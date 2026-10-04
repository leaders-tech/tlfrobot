"""Library errors. Each has a stable `code`, a message a student can read and
structured `details` (the offending cell, direction, line, …)."""
from __future__ import annotations


class RobotError(Exception):
    code = "ROBOT_ERROR"
    #: A world error ends the session: catching it does not bring the robot back.
    terminal = True

    def __init__(self, message: str, **details):
        super().__init__(message)
        self.message = message
        self.details = details

    def as_json(self) -> dict:
        out = {"code": self.code, "message": self.message}
        if self.details:
            out["details"] = self.details
        return out


def _error(code: str, terminal: bool = True) -> type[RobotError]:
    name = "".join(part.capitalize() for part in code.split("_")) + "Error"
    return type(name, (RobotError,), {"code": code, "terminal": terminal})


WorldNotLoadedError = _error("WORLD_NOT_LOADED", terminal=False)
CommandUnavailableError = _error("COMMAND_UNAVAILABLE")
WallCollisionError = _error("WALL_COLLISION")
NoCrystalError = _error("NO_CRYSTAL")
EmptyBagError = _error("EMPTY_BAG")
SessionFailedError = _error("SESSION_FAILED")
InvalidArgumentError = _error("INVALID_ARGUMENT")
CallLimitError = _error("CALL_LIMIT")
TraceLimitError = _error("TRACE_LIMIT")
OutputLimitError = _error("OUTPUT_LIMIT")
StateLimitError = _error("STATE_LIMIT")
NumberRangeError = _error("NUMBER_RANGE")
CancelledError = _error("CANCELLED")
RuntimeFailureError = _error("RUNTIME_FAILURE")


class MapError(RobotError):
    """An invalid world, goal or input document. Raised before anything runs."""

    code = "MAP_INVALID"
    terminal = False

    def __init__(self, message: str, *, path: str | None = None, line: int | None = None,
                 column: int | None = None, **details):
        where = []
        if path:
            where.append(path)
        if line is not None:
            where.append(f"line {line}" + (f", column {column}" if column is not None else ""))
        full = f"{'; '.join(where)}: {message}" if where else message
        super().__init__(full, **{k: v for k, v in
                                 dict(path=path, line=line, column=column, **details).items()
                                 if v is not None})


BY_CODE = {cls.code: cls for cls in (
    WorldNotLoadedError, CommandUnavailableError, WallCollisionError, NoCrystalError,
    EmptyBagError, SessionFailedError, InvalidArgumentError, CallLimitError, TraceLimitError,
    OutputLimitError, StateLimitError, NumberRangeError, CancelledError, RuntimeFailureError,
    MapError,
)}

#: Codes a replayed world operation can legitimately fail with.
WORLD_CODES = frozenset({"COMMAND_UNAVAILABLE", "WALL_COLLISION", "NO_CRYSTAL", "EMPTY_BAG",
                         "NUMBER_RANGE"})
