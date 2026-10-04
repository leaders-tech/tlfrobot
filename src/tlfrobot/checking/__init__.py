"""Checking a run: strict trace parsing, independent replay from the trusted
world, and goal evaluation. Nothing a trace claims is trusted; every call is
re-executed by the same rules the runtime used."""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Iterable

from .. import catalog, core, maps
from ..errors import MapError, RobotError
from ..trace import TRACE_VERSION

MAX_RECORD_BYTES = 16 << 20
MAX_TRACE_BYTES = 64 << 20
REACH_BOUND = 1_000_000

ACCEPTED, WRONG_ANSWER, PRESENTATION_ERROR, CHECKER_ERROR = (
    "accepted", "wrong_answer", "presentation_error", "checker_error")


class TraceFormatError(Exception):
    """The output is not a well-formed trace (presentation error)."""

    def __init__(self, message: str, line: int | None = None):
        super().__init__(f"line {line}: {message}" if line else message)
        self.line = line


class Rejected(Exception):
    """A well-formed trace of an illegal or dishonest run (wrong answer)."""

    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass
class ReplayResult:
    state: core.State
    status: str
    calls: int
    visits: list[maps.Cell]
    revisited: bool
    error: dict | None
    output: str


@dataclass
class CheckResult:
    verdict: str
    code: str
    message: str
    details: dict = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.verdict == ACCEPTED

    def as_json(self) -> dict:
        return {"verdict": self.verdict, "code": self.code, "message": self.message,
                "details": self.details}


# --------------------------------------------------------------------------- parsing

def _no_dup(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise ValueError(f"duplicate key {k!r}")
        out[k] = v
    return out


def _bad_constant(name):
    raise ValueError(f"{name} is not allowed")


def _loads(line: str, lineno: int) -> dict:
    try:
        obj = json.loads(line, object_pairs_hook=_no_dup, parse_constant=_bad_constant)
    except ValueError as e:
        raise TraceFormatError(f"not valid JSON: {e}", lineno) from None
    if not isinstance(obj, dict):
        raise TraceFormatError("a record must be a JSON object", lineno)
    return obj


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _shape(rec: dict, lineno: int, required: dict, optional: dict) -> None:
    for k, typ in required.items():
        if k not in rec:
            raise TraceFormatError(f"{rec.get('t')!r} record is missing {k!r}", lineno)
        if not typ(rec[k]):
            raise TraceFormatError(f"{rec.get('t')!r} record has a bad {k!r}", lineno)
    for k, v in rec.items():
        if k in required:
            continue
        if k not in optional:
            raise TraceFormatError(f"{rec.get('t')!r} record has an unknown field {k!r}", lineno)
        if not optional[k](v):
            raise TraceFormatError(f"{rec.get('t')!r} record has a bad {k!r}", lineno)


_NN = lambda v: _is_int(v) and v >= 0  # noqa: E731
_STR = lambda v: isinstance(v, str)  # noqa: E731
_DICT = lambda v: isinstance(v, dict)  # noqa: E731
_TYPES = {
    "start": ({"t": _STR, "s": _NN, "v": _is_int, "world": _DICT, "actor": _STR, "controller": _STR,
               "source": _STR}, {}),
    "call": ({"t": _STR, "s": _NN, "n": _NN, "op": _STR, "rev": _NN},
             {"result": lambda v: v is None or isinstance(v, (bool, int)), "line": _NN, "column": _NN,
              "end_line": _NN, "end_column": _NN, "error": _DICT, "cancelled": lambda v: v is True,
              "args": lambda v: isinstance(v, list)}),
    "output": ({"t": _STR, "s": _NN, "stream": lambda v: v in ("stdout", "stderr"), "text": _STR}, {}),
    "end": ({"t": _STR, "s": _NN, "status": lambda v: v in ("completed", "error", "cancelled", "limit"),
             "rev": _NN, "calls": _NN, "state": _DICT}, {"error": _DICT}),
}


def parse_trace(stream: IO[bytes] | IO[str] | Iterable, *, max_bytes: int = MAX_TRACE_BYTES) -> list[dict]:
    """Parse and frame-check a complete trace. Raises TraceFormatError."""
    records: list[dict] = []
    total = 0
    for lineno, raw in enumerate(stream, 1):
        if isinstance(raw, bytes):
            total += len(raw)
            if len(raw) > MAX_RECORD_BYTES:
                raise TraceFormatError("record too long", lineno)
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                raise TraceFormatError("not valid UTF-8", lineno) from None
        else:
            total += len(raw.encode("utf-8", "surrogatepass"))
        if total > max_bytes:
            raise TraceFormatError("trace too long", lineno)
        if not raw.endswith("\n"):
            raise TraceFormatError("the last record is not newline-terminated (truncated output?)", lineno)
        line = raw[:-1]
        if line.endswith("\r"):
            raise TraceFormatError("CR characters are not allowed", lineno)
        if lineno == 1 and line.startswith("﻿"):
            raise TraceFormatError("a BOM is not allowed", lineno)
        if not line.strip():
            raise TraceFormatError("blank lines are not allowed", lineno)
        rec = _loads(line, lineno)
        t = rec.get("t")
        if t not in _TYPES:
            raise TraceFormatError(f"unknown record type {t!r}", lineno)
        _shape(rec, lineno, *_TYPES[t])
        if rec["s"] != len(records):
            raise TraceFormatError(f"record number s={rec['s']}, expected {len(records)}", lineno)
        if (t == "start") != (len(records) == 0):
            raise TraceFormatError("the first record, and only it, must be 'start'", lineno)
        if records and records[-1]["t"] == "end":
            raise TraceFormatError("records after 'end'", lineno)
        if t == "start" and rec["v"] != TRACE_VERSION:
            raise TraceFormatError(f"trace version {rec['v']} is not supported", lineno)
        records.append(rec)
    if not records:
        raise TraceFormatError("empty output: no trace at all")
    if records[-1]["t"] != "end":
        raise TraceFormatError("no 'end' record (the program was killed or the output truncated)")
    return records


# --------------------------------------------------------------------------- replay

def replay(world: maps.World, records: list[dict]) -> ReplayResult:
    """Re-execute every call from `world`'s initial state; raise Rejected on any
    disagreement between the trace and the rules."""
    start = records[0]
    if start["world"] != world.normalised():
        raise Rejected("WORLD_MISMATCH", "the trace was produced on a different world than this test")
    state = core.State.initial(world)
    visits = [world.robot_at]
    visited = {world.robot_at}
    revisited = False
    n = 0
    stopped: str | None = None  # status implied by a terminal call
    error: dict | None = None
    out: list[str] = []
    for rec in records[1:-1]:
        t = rec["t"]
        if t == "output":
            out.append(rec["text"])
            continue
        if t != "call":
            raise Rejected("BAD_SEQUENCE", f"unexpected {t!r} record before the end")
        n += 1
        if rec["n"] != n:
            raise Rejected("BAD_SEQUENCE", f"call number {rec['n']}, expected {n}")
        if stopped is not None:
            raise Rejected("CALL_AFTER_STOP", f"call {n} ({rec['op']}) after the run had already stopped")
        op = rec["op"]
        where = {"call": n, "op": op, **({"line": rec["line"]} if "line" in rec else {})}
        if op not in catalog.BY_NAME:
            raise Rejected("UNKNOWN_OPERATION", f"unknown operation {op!r}", **where)
        try:
            tx = core.prepare(world, state, op)
            terr = tx.error
        except RobotError as e:
            tx, terr = None, e
        if "cancelled" in rec:
            stopped = "cancelled"
            if rec["rev"] != state.rev or "result" in rec or "error" in rec:
                raise Rejected("BAD_RECORD", f"call {n} is cancelled but claims an outcome", **where)
            continue
        claimed = rec.get("error")
        if terr is not None:
            if claimed is None or claimed.get("code") != terr.code:
                raise Rejected("ILLEGAL_ACTION", f"{op}() at call {n} is not possible here: {terr.message}",
                               **where, error_code=terr.code)
            if rec["rev"] != state.rev:
                raise Rejected("BAD_RECORD", f"call {n}: a failed call cannot change the revision", **where)
            stopped = "limit" if terr.code == "NUMBER_RANGE" else "error"
            error = claimed
            continue
        if claimed is not None:
            code = claimed.get("code")
            if code in ("CALL_LIMIT", "TRACE_LIMIT", "STATE_LIMIT", "OUTPUT_LIMIT") and rec["rev"] == state.rev:
                stopped = "limit"
                error = claimed
                continue
            raise Rejected("FORGED_ERROR", f"call {n} ({op}) reports an error {code!r} that did not happen",
                           **where)
        if tx.kind == "sensor":
            if "result" not in rec or type(rec["result"]) is not type(tx.result) or rec["result"] != tx.result:
                raise Rejected("FORGED_RESULT",
                               f"{op}() at call {n} returned {tx.result!r}, the trace says {rec.get('result')!r}",
                               **where)
        elif "result" in rec:
            raise Rejected("BAD_RECORD", f"call {n}: {op}() returns nothing", **where)
        if tx.after is not None:
            moved = tx.after.at != state.at
            state = tx.after
            if moved:
                if state.at in visited:
                    revisited = True
                visited.add(state.at)
                visits.append(state.at)
        if rec["rev"] != state.rev:
            raise Rejected("BAD_RECORD", f"call {n}: revision {rec['rev']}, expected {state.rev}", **where)
    end = records[-1]
    if end["calls"] != n:
        raise Rejected("BAD_SEQUENCE", f"the end record counts {end['calls']} calls, the trace has {n}")
    if end["rev"] != state.rev:
        raise Rejected("BAD_SEQUENCE", "the end record's revision disagrees with the replay")
    if end["state"] != state.compact():
        raise Rejected("FORGED_STATE", "the final state in the trace is not where the calls lead")
    status = end["status"]
    if stopped is not None:
        if status != stopped:
            raise Rejected("FORGED_STATUS", f"the run stopped with {stopped!r} but the end record says {status!r}")
    elif status == "error" and "error" not in end:
        raise Rejected("BAD_RECORD", "an unsuccessful end needs an error")
    if status != "completed":
        error = end.get("error", error)
    return ReplayResult(state, status, n, visits, revisited, error, "".join(out))


# --------------------------------------------------------------------------- goals

def reachable(world: maps.World, start: maps.Cell, bound: int = REACH_BOUND) -> set[maps.Cell] | None:
    seen = {start}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        for d, (dx, dy) in core.STEP.items():
            if world.blocked(cell, d):
                continue
            nxt = (cell[0] + dx, cell[1] + dy)
            if nxt not in seen:
                if len(seen) >= bound:
                    return None
                seen.add(nxt)
                queue.append(nxt)
    return seen


def evaluate_goal(world: maps.World, result: ReplayResult, goal: maps.Goal | None) -> CheckResult:
    if result.status != "completed":
        err = result.error or {}
        msg = err.get("message") or f"the run ended with status {result.status!r}"
        details = {"status": result.status}
        if err:
            details["error"] = err
        return CheckResult(WRONG_ANSWER, err.get("code", result.status.upper()), msg, details)
    if goal is None:
        return CheckResult(CHECKER_ERROR, "NO_GOAL", "this task has no goal configured")
    s = result.state
    miss: list[dict] = []

    def cell_s(c):
        return f"({c[0]}, {c[1]})"

    if goal.robot_at is not None and s.at != goal.robot_at:
        miss.append({"what": "robot_at", "expected": list(goal.robot_at), "actual": list(s.at),
                     "message": f"the robot should finish at {cell_s(goal.robot_at)}, it is at {cell_s(s.at)}"})
    if goal.robot_heading is not None and s.heading != goal.robot_heading:
        miss.append({"what": "robot_heading", "expected": goal.robot_heading, "actual": s.heading,
                     "message": f"the robot should face {goal.robot_heading}, it faces {s.heading}"})
    if goal.has_bag and s.bag != goal.bag:
        miss.append({"what": "bag", "expected": goal.bag, "actual": s.bag,
                     "message": f"the bag should hold {goal.bag}, it holds {s.bag}"})
    if goal.crystals_mode is not None:
        expected = dict(world.crystals) if goal.crystals_mode == "unchanged" else goal.crystals
        cells = set(expected) | (set(s.crystals) if goal.crystals_mode != "specified" else set())
        for c in sorted(cells, key=lambda c: (c[1], c[0])):
            want, have = expected.get(c, 0), s.crystals.get(c, 0)
            if want != have:
                miss.append({"what": "crystals", "cell": list(c), "expected": want, "actual": have,
                             "message": f"cell {cell_s(c)} should have {want} crystal(s), it has {have}"})
    if goal.paint_mode is not None:
        expected = set(world.painted) if goal.paint_mode == "unchanged" else goal.paint
        for c in sorted(expected - s.painted, key=lambda c: (c[1], c[0])):
            miss.append({"what": "paint", "cell": list(c), "expected": True, "actual": False,
                         "message": f"cell {cell_s(c)} should be painted"})
        if goal.paint_mode != "contains":
            for c in sorted(s.painted - expected, key=lambda c: (c[1], c[0])):
                miss.append({"what": "paint", "cell": list(c), "expected": False, "actual": True,
                             "message": f"cell {cell_s(c)} should not be painted"})
    visited = set(result.visits)
    if goal.visits_mode is not None:
        if goal.visits_mode == "all_reachable":
            want = reachable(world, world.robot_at)
            if want is None:
                return CheckResult(CHECKER_ERROR, "UNBOUNDED_REACH",
                                   "the reachable area is not finite within the checker's bound")
        else:
            want = goal.visits
        for c in sorted(want - visited, key=lambda c: (c[1], c[0])):
            miss.append({"what": "visits", "cell": list(c), "message": f"cell {cell_s(c)} was never visited"})
            if len(miss) > 50:
                break
        if goal.visits_mode == "exact":
            for c in sorted(visited - want, key=lambda c: (c[1], c[0])):
                miss.append({"what": "visits", "cell": list(c),
                             "message": f"cell {cell_s(c)} should not have been visited"})
    if goal.forbid_revisits and result.revisited:
        miss.append({"what": "revisit", "message": "the robot entered a cell it had already visited"})
    if miss:
        first = miss[0]["message"]
        more = f" (and {len(miss) - 1} more)" if len(miss) > 1 else ""
        return CheckResult(WRONG_ANSWER, "GOAL_NOT_MET", first[0].upper() + first[1:] + more,
                           {"mismatches": miss[:100]})
    return CheckResult(ACCEPTED, "OK", "the goal is reached")


# --------------------------------------------------------------------------- high level

def check_records(world: maps.World, records: list[dict], goal: maps.Goal | None) -> CheckResult:
    try:
        res = replay(world, records)
    except Rejected as r:
        return CheckResult(WRONG_ANSWER, r.code, r.message, r.details)
    return evaluate_goal(world, res, goal)


def check_stream(world: maps.World, stream, goal: maps.Goal | None) -> CheckResult:
    try:
        records = parse_trace(stream)
    except TraceFormatError as e:
        return CheckResult(PRESENTATION_ERROR, "BAD_TRACE", str(e))
    return check_records(world, records, goal)


def check_files(map_path: str | Path, trace_path: str | Path, *, goal_path: str | Path | None = None) -> CheckResult:
    try:
        world = maps.load_world(map_path)
        goal = maps.load_goal(goal_path, world) if goal_path is not None else world.goal
    except (MapError, OSError) as e:
        return CheckResult(CHECKER_ERROR, "BAD_TASK", f"invalid task files: {e}")
    with open(trace_path, "rb") as fh:
        return check_stream(world, fh, goal)
