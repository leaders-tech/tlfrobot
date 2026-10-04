import io
import json
import textwrap

import pytest

from tlfrobot import maps
from tlfrobot.runtime import run_source


def world(text: str) -> maps.World:
    return maps.loads_world(textwrap.dedent(text))


def run(src: str, w: maps.World):
    lines: list[str] = []
    res = run_source(textwrap.dedent(src), w, sink=lines.append, keep_records=True)
    return res, lines


def trace_bytes(lines: list[str]) -> io.BytesIO:
    return io.BytesIO("".join(lines).encode())


def edit(lines: list[str], index: int, **changes) -> list[str]:
    out = list(lines)
    rec = json.loads(out[index])
    for k, v in changes.items():
        if v is ...:
            rec.pop(k, None)
        else:
            rec[k] = v
    out[index] = json.dumps(rec, separators=(",", ":")) + "\n"
    return out


CORRIDOR = """
format = "tlfrobot-world/1"
id = "corridor"
[rules]
movement = "relative"
tools = ["crystals"]
sensors = ["counts"]
[board]
size = [5, 1]
[robot]
at = [0, 0]
heading = "east"
bag = 0
[cells]
crystals = [{ at = [2, 0], count = 2 }]
[goal]
robot_at = [4, 0]
bag = 2
[goal.crystals]
mode = "exact"
cells = []
"""


@pytest.fixture
def corridor():
    return world(CORRIDOR)
