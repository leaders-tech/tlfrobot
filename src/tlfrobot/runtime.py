"""Sessions: running a student's program against one world.

A Session owns the authoritative state. Every robot call goes through
`Session.call`: check, prepare, show it through the transport, commit on
completion, record. Transports differ only in how a prepared call is shown:
headless completes it at once, the browser animates it and answers through
shared memory.
"""
from __future__ import annotations

import atexit
import builtins
import io
import os
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import core, maps
from .errors import (CallLimitError, CommandUnavailableError, MapError, OutputLimitError,
                     RobotError, SessionFailedError, StateLimitError, TraceLimitError,
                     WorldNotLoadedError)
from .trace import TRACE_VERSION, TraceWriter

ACTOR, CONTROLLER = "robot", "student"
HOST_LIMITS = {
    "max_calls": 100_000,
    "max_trace_bytes": 32 << 20,
    "max_output_bytes": 1 << 20,
    "max_state_cells": 100_000,
    "max_wait_us": 3_600_000_000,
    "max_compute_ms": 5_000,
}
RUN_HINT = "Run your program with:  python -m tlfrobot run solution.py"


class Cancelled(BaseException):
    """Stop was pressed. A BaseException, so `except Exception` cannot swallow it."""


def effective_limits(world: maps.World, host: dict[str, int] | None = None) -> dict[str, int]:
    out = dict(HOST_LIMITS)
    if host:
        out.update(host)
    for k, v in world.limits.items():
        out[k] = min(out[k], v)
    return out


# --------------------------------------------------------------------------- transports

class Transport:
    """Shows a prepared call and says how it ended: completed or cancelled."""

    def perform(self, request: dict) -> str:
        return "completed"

    def finished(self, end: dict) -> None:
        pass


class HeadlessTransport(Transport):
    pass


class CallbackTransport(Transport):
    """`perform` is a function returning "completed" or "cancelled" (the browser's bridge)."""

    def __init__(self, perform: Callable[[dict], str], finished: Callable[[dict], None] | None = None):
        self._perform = perform
        self._finished = finished

    def perform(self, request: dict) -> str:
        return self._perform(request)

    def finished(self, end: dict) -> None:
        if self._finished:
            self._finished(end)


# --------------------------------------------------------------------------- session

@dataclass
class RunResult:
    status: str  # completed | error | cancelled | limit
    error: dict | None
    state: core.State
    calls: int
    visits: list[maps.Cell]
    revisited: bool
    records: list[dict] | None = None
    exit_code: int = 0


class Session:
    def __init__(self, world: maps.World, *, filename: str = "solution.py",
                 transport: Transport | None = None, writer: TraceWriter | None = None,
                 limits: dict[str, int] | None = None, code_filename: str | None = None):
        self.world = world
        self.filename = filename
        self.code_filename = code_filename or filename
        self.transport = transport or HeadlessTransport()
        self.limits = effective_limits(world, limits)
        self.writer = writer
        if writer is not None and writer.max_bytes is None:
            writer.max_bytes = self.limits["max_trace_bytes"]
        self.state = core.State.initial(world)
        self.status = "running"  # running | error | cancelled | limit | completed
        self.error: RobotError | None = None
        self.n = 0
        self.output_bytes = 0
        self.visits: list[maps.Cell] = [world.robot_at]
        self._visited = {world.robot_at}
        self.revisited = False
        self.ended = False
        self.end_error: dict | None = None
        if writer is not None:
            writer.write({"t": "start", "v": TRACE_VERSION, "world": world.normalised(),
                          "actor": ACTOR, "controller": CONTROLLER, "source": filename})

    # -- helpers
    def _line(self) -> int | None:
        frame = sys._getframe(2)
        while frame is not None:
            if frame.f_code.co_filename == self.code_filename:
                return frame.f_lineno
            frame = frame.f_back
        return None

    def _record(self, rec: dict) -> None:
        if self.writer is not None:
            self.writer.write(rec)

    def _fail(self, error: RobotError, status: str = "error") -> RobotError:
        if self.status == "running":
            self.status = status
            self.error = error
        return error

    # -- the one entry point for robot functions
    def call(self, op: str, *, line: int | None = None) -> Any:
        if self.status != "running":
            if self.status == "cancelled":
                raise Cancelled()
            raise SessionFailedError(
                f"{op}(): the robot already stopped after an earlier error"
                + (f" ({self.error.code})" if self.error else ""))
        if line is None:
            line = self._line()
        if self.n + 1 > self.limits["max_calls"]:
            raise self._fail(CallLimitError(f"more than {self.limits['max_calls']} robot calls"), "limit")
        rec: dict = {"t": "call", "n": self.n + 1, "op": op}
        if self.writer is not None and not self.writer.fits(rec):
            raise self._fail(TraceLimitError("the trace is too long"), "limit")
        try:
            tx = core.prepare(self.world, self.state, op)
        except CommandUnavailableError as e:
            self.n += 1
            self._record({**rec, "rev": self.state.rev, "error": e.as_json(), **_where(line)})
            raise self._fail(e)
        except RobotError as e:  # NUMBER_RANGE
            self.n += 1
            self._record({**rec, "rev": self.state.rev, "error": e.as_json(), **_where(line)})
            raise self._fail(e, "limit")
        if tx.after is not None and tx.after.state_cells() > self.limits["max_state_cells"]:
            err = StateLimitError(f"more than {self.limits['max_state_cells']} non-empty cells")
            self.n += 1
            self._record({**rec, "rev": self.state.rev, "error": err.as_json(), **_where(line)})
            raise self._fail(err, "limit")
        self.n += 1
        request = {"n": self.n, "op": op, "kind": tx.kind, "line": line, "fx": tx.fx,
                   "rev": self.state.rev}
        if tx.kind == "sensor":
            request["result"] = tx.result
        if tx.error is not None:
            request["error"] = tx.error.as_json()
        outcome = self.transport.perform(request)
        if outcome == "cancelled":
            self._record({**rec, "rev": self.state.rev, "cancelled": True, **_where(line)})
            self.status = "cancelled"
            raise Cancelled()
        if tx.error is not None:
            self._record({**rec, "rev": self.state.rev, "error": tx.error.as_json(), **_where(line)})
            raise self._fail(tx.error)
        if tx.after is not None:
            moved = tx.after.at != self.state.at
            self.state = tx.after
            if moved:
                cell = self.state.at
                if cell in self._visited:
                    self.revisited = True
                self._visited.add(cell)
                self.visits.append(cell)
        out = {**rec, "rev": self.state.rev}
        if tx.kind == "sensor":
            out["result"] = tx.result
        self._record({**out, **_where(line)})
        return tx.result

    def output(self, stream: str, text: str) -> None:
        if not text:
            return
        size = len(text.encode("utf-8", "surrogatepass"))
        if self.output_bytes + size > self.limits["max_output_bytes"]:
            raise self._fail(OutputLimitError("the program printed too much"), "limit")
        self.output_bytes += size
        rec = {"t": "output", "stream": stream, "text": text}
        if self.writer is not None and not self.writer.fits(rec):
            raise self._fail(TraceLimitError("the trace is too long"), "limit")
        self._record(rec)

    def end(self, status: str | None = None, error: dict | None = None) -> dict:
        if self.ended:
            return {}
        self.ended = True
        if status is not None and self.status in ("running", "completed"):
            self.status = status
        if self.status == "running":
            self.status = "completed"
        if error is None and self.error is not None:
            error = self.error.as_json()
        self.end_error = error if self.status != "completed" else None
        rec = {"t": "end", "status": self.status, "rev": self.state.rev, "calls": self.n,
               "state": self.state.compact()}
        if error is not None and self.status != "completed":
            rec["error"] = error
        if self.writer is not None:
            rec = self.writer.write(rec)
        self.transport.finished(rec)
        return rec

    def result(self, exit_code: int = 0) -> RunResult:
        err = self.error.as_json() if self.error else self.end_error
        return RunResult(self.status, err, self.state, self.n, list(self.visits), self.revisited,
                         self.writer.records if self.writer else None, exit_code)


def _where(line: int | None) -> dict:
    return {"line": line} if line is not None else {}


# --------------------------------------------------------------------------- current session

_current: Session | None = None


def current() -> Session:
    if _current is None:
        raise WorldNotLoadedError("No robot world is loaded. " + RUN_HINT)
    return _current


def call(op: str) -> Any:
    session = _current
    if session is None:
        raise WorldNotLoadedError(f"{op}(): no robot world is loaded. " + RUN_HINT)
    return session.call(op)


class _OutputStream(io.TextIOBase):
    """Student `print` → `output` records, a line at a time."""

    def __init__(self, session: Session, stream: str):
        self.session = session
        self.stream = stream
        self.buf = ""

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            raise TypeError(f"write() argument must be str, not {type(text).__name__}")
        self.buf += text
        if "\n" in self.buf:
            head, _, self.buf = self.buf.rpartition("\n")
            self.session.output(self.stream, head + "\n")
        elif len(self.buf) > 8192:
            self.flush()
        return len(text)

    def flush(self) -> None:
        if self.buf:
            text, self.buf = self.buf, ""
            self.session.output(self.stream, text)

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return "utf-8"


def _python_error(exc: BaseException, code_filename: str) -> dict:
    tb = exc.__traceback__
    frames = [f for f in traceback.extract_tb(tb) if f.filename == code_filename]
    line = frames[-1].lineno if frames else None
    if isinstance(exc, SyntaxError) and exc.filename == code_filename:
        line = exc.lineno
    text = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    details: dict = {"type": type(exc).__name__}
    if line is not None:
        details["line"] = line
    shown = traceback.StackSummary.from_list(frames).format() if frames else []
    details["traceback"] = "Traceback (most recent call last):\n" + "".join(shown) + text + "\n" \
        if frames else text + "\n"
    return {"code": "PYTHON_EXCEPTION", "message": text, "details": details}


def run_source(source: str, world: maps.World, *, filename: str = "solution.py",
               transport: Transport | None = None, sink: Callable[[str], None] | None = None,
               keep_records: bool = False, capture_output: bool = True,
               limits: dict[str, int] | None = None, globals_extra: dict | None = None) -> RunResult:
    """Run `source` as a fresh `__main__` against `world`."""
    global _current
    writer = None
    if sink is not None or keep_records:
        writer = TraceWriter(sink or (lambda line: None))
        if keep_records:
            writer.keep()
    session = Session(world, filename=filename, transport=transport, writer=writer, limits=limits)
    try:
        code = compile(source, filename, "exec", dont_inherit=True)
    except SyntaxError as e:
        session.status = "error"
        session.end(error=_python_error(e, filename))
        return session.result(1)
    namespace = {"__name__": "__main__", "__builtins__": builtins, "__file__": filename}
    if globals_extra:
        namespace.update(globals_extra)
    saved = _current, sys.stdout, sys.stderr
    _current = session
    out = err = None
    if capture_output:
        out, err = _OutputStream(session, "stdout"), _OutputStream(session, "stderr")
        sys.stdout, sys.stderr = out, err
    py_error: dict | None = None
    exit_code = 0
    try:
        exec(code, namespace)
    except SystemExit as e:
        if e.code not in (None, 0):
            py_error = {"code": "PYTHON_EXCEPTION", "message": f"SystemExit: {e.code}",
                        "details": {"type": "SystemExit"}}
    except (Cancelled, KeyboardInterrupt):
        session.status = "cancelled" if session.status in ("running", "completed") else session.status
    except RobotError as e:
        session._fail(e)
    except BaseException as e:  # noqa: BLE001 - a student's program can raise anything
        py_error = _python_error(e, filename)
    finally:
        for s in (out, err):
            if s is not None:
                try:
                    s.flush()
                except RobotError:
                    pass
        _current, sys.stdout, sys.stderr = saved
    if py_error is not None and session.status == "running":
        session.status = "error"
        session.end(error=py_error)
    else:
        session.end()
    if session.status != "completed":
        exit_code = 1
    return session.result(exit_code)


def run_file(path: str | os.PathLike, *, map_source: str | None = None, mode: str = "headless",
             trace_path: str | None = None) -> int:
    """Infrastructure entry point. Returns a process exit status:
    0 completed, 1 student/world failure, 2 invalid invocation or map."""
    src_path = Path(path)
    try:
        source = src_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"tlfrobot: cannot read {src_path}: {e}", file=sys.stderr)
        return 2
    try:
        world = resolve_map(src_path, map_source)
    except (MapError, OSError) as e:
        print(f"tlfrobot: {e}", file=sys.stderr)
        return 2
    if mode not in ("headless", "ejudge"):
        print(f"tlfrobot: mode {mode!r} is not available in this release (use headless)", file=sys.stderr)
        return 2
    real_out = sys.stdout
    if trace_path:
        fh = open(trace_path, "w", encoding="utf-8")
        sink = fh.write
    else:
        fh = None
        sink = real_out.write
    try:
        res = run_source(source, world, filename=src_path.name, sink=sink)
    finally:
        if fh:
            fh.close()
        real_out.flush()
    if res.error and res.error.get("code") == "PYTHON_EXCEPTION":
        tb = res.error.get("details", {}).get("traceback")
        if tb:
            sys.stderr.write(tb)
    if mode == "ejudge":
        return 0
    return res.exit_code


def resolve_map(source_path: Path, map_source: str | None) -> maps.World:
    if map_source is None:
        map_source = os.environ.get("TLFROBOT_MAP")
    if map_source == "-":
        return maps.loads_world(sys.stdin.buffer.read(maps.MAX_MAP_BYTES + 1), path="<stdin>")
    if map_source is not None:
        return maps.load_world(Path(map_source))
    adjacent = source_path.parent / "map.toml"
    if not adjacent.exists():
        raise MapError(f"no map given and no map.toml next to {source_path.name}")
    return maps.load_world(adjacent)


# --------------------------------------------------------------------------- ejudge auto mode

def _main_file() -> str | None:
    main = sys.modules.get("__main__")
    return getattr(main, "__file__", None)


def start_ejudge_auto() -> None:
    """`TLFROBOT_MODE=ejudge`: the submitted file is run directly by the judge's
    python3. Importing tlfrobot reads the world from stdin, starts the session and
    arranges for the end record. Student print() becomes output records."""
    global _current
    main_file = _main_file()
    if main_file is None or sys.argv[:1] == ["-m"]:
        return
    try:
        world = maps.loads_world(sys.stdin.buffer.read(maps.MAX_MAP_BYTES + 1), path="<stdin>")
    except MapError as e:
        sys.stderr.write(f"tlfrobot: invalid test world: {e}\n")
        sys.stderr.flush()
        os._exit(3)
    real_out = sys.stdout

    def sink(line: str) -> None:
        real_out.write(line)

    writer = TraceWriter(sink)
    session = Session(world, filename=os.path.basename(main_file), writer=writer,
                      code_filename=main_file)
    _current = session
    out = _OutputStream(session, "stdout")
    sys.stdout = out
    previous_hook = sys.excepthook

    def finish(status: str | None = None, error: dict | None = None) -> None:
        try:
            out.flush()
        except RobotError:
            pass
        session.end(status, error)
        real_out.flush()

    def hook(exc_type, exc, tb):
        if isinstance(exc, (Cancelled, KeyboardInterrupt)):
            finish("cancelled")
            previous_hook(exc_type, exc, tb)
            return
        if isinstance(exc, RobotError):
            # A world error is the student's mistake in the task, not a crash:
            # write a complete end record and let the checker explain it.
            session._fail(exc)
            finish()
            sys.stderr.write(f"{exc.code}: {exc.message}\n")
            sys.stderr.flush()
            os._exit(0)
        session.status = "error" if session.status == "running" else session.status
        finish(error=_python_error(exc, main_file))
        previous_hook(exc_type, exc, tb)

    sys.excepthook = hook
    atexit.register(finish)
