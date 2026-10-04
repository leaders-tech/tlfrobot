"""The compact NDJSON trace, `tlfrobot-trace/2`: one JSON object per line."""
from __future__ import annotations

import json
from typing import Callable

TRACE_VERSION = 2
TRACE_FORMAT = "tlfrobot-trace/2"
END_RESERVE = 1 << 20  # bytes kept for the end record's final state


def dumps(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class TraceWriter:
    """Numbers records (`s`) and hands complete lines to `sink`."""

    def __init__(self, sink: Callable[[str], None], *, max_bytes: int | None = None):
        self.sink = sink
        self.max_bytes = max_bytes
        self.s = 0
        self.bytes = 0
        self.records: list[dict] | None = None

    def keep(self) -> "TraceWriter":
        """Also keep the records in memory (the browser checks them in place)."""
        self.records = []
        return self

    def fits(self, record: dict, *, reserve: int = END_RESERVE) -> bool:
        if self.max_bytes is None:
            return True
        return self.bytes + len(dumps(record).encode()) + 1 + reserve <= self.max_bytes

    def write(self, record: dict) -> dict:
        record = {"t": record["t"], "s": self.s, **{k: v for k, v in record.items() if k != "t"}}
        line = dumps(record) + "\n"
        self.bytes += len(line.encode())
        self.s += 1
        self.sink(line)
        if self.records is not None:
            self.records.append(record)
        return record
