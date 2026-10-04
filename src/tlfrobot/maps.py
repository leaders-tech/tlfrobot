"""World, goal and input documents: strict parsing, validation and the
normalised JSON form every runtime and the checker share.

Coordinates: x grows east, y grows north. A bounded board's origin is its
south-west cell. A wall is a run of unit cell edges: `axis = "h"` fixes y
(the line between rows y-1 and y) and spans x; `axis = "v"` fixes x and spans y.
`span = [a, b]` covers edges a <= k < b.
"""
from __future__ import annotations

import bisect
import math
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Iterable

from . import catalog
from .errors import MapError

WORLD_FORMAT = "tlfrobot-world/1"
GOAL_FORMAT = "tlfrobot-goal/1"
INPUT_FORMAT = "tlfrobot-input/1"

SAFE = 2**53 - 1
MAX_MAP_BYTES = 1 << 20
MAX_BOARD_SIDE = 10_000
MAX_WALLS = 100_000
HEADINGS = ("north", "east", "south", "west")
MARKER_KINDS = ("start", "finish", "target")
LIMIT_KEYS = ("max_calls", "max_trace_bytes", "max_output_bytes", "max_state_cells",
              "max_wait_us", "max_compute_ms")
NEG_INF = -math.inf
POS_INF = math.inf
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}")

Cell = tuple[int, int]


# --------------------------------------------------------------------------- walls

class Walls:
    """Unions of half-open edge intervals per wall line. Endpoints may be ±inf."""

    def __init__(self) -> None:
        self._lines: dict[tuple[str, int], list[tuple[float, float]]] = {}
        self._starts: dict[tuple[str, int], list[float]] = {}

    @classmethod
    def from_intervals(cls, items: Iterable[tuple[str, int, float, float]]) -> "Walls":
        walls = cls()
        grouped: dict[tuple[str, int], list[tuple[float, float]]] = {}
        for axis, at, a, b in items:
            if a < b:
                grouped.setdefault((axis, at), []).append((a, b))
        for key, spans in grouped.items():
            spans.sort()
            merged: list[list[float]] = []
            for a, b in spans:
                if merged and a <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], b)
                else:
                    merged.append([a, b])
            walls._lines[key] = [(a, b) for a, b in merged]
            walls._starts[key] = [a for a, _ in merged]
        return walls

    def has(self, axis: str, at: int, k: int) -> bool:
        spans = self._lines.get((axis, at))
        if not spans:
            return False
        i = bisect.bisect_right(self._starts[(axis, at)], k) - 1
        return i >= 0 and spans[i][0] <= k < spans[i][1]

    def intervals(self) -> list[tuple[str, int, float, float]]:
        out = [(axis, at, a, b) for (axis, at), spans in self._lines.items() for a, b in spans]
        out.sort(key=lambda w: (w[0], w[1], w[2]))
        return out

    def count(self) -> int:
        return sum(len(s) for s in self._lines.values())


def _token(v: float) -> int | str:
    if v == NEG_INF:
        return "-inf"
    if v == POS_INF:
        return "+inf"
    return int(v)


# --------------------------------------------------------------------------- data

@dataclass
class Goal:
    robot_at: Cell | None = None
    robot_heading: str | None = None
    bag: int | str | None = None
    has_bag: bool = False
    crystals_mode: str | None = None
    crystals: dict[Cell, int] = field(default_factory=dict)
    paint_mode: str | None = None
    paint: set[Cell] = field(default_factory=set)
    visits_mode: str | None = None
    visits: set[Cell] = field(default_factory=set)
    forbid_revisits: bool = False


@dataclass
class World:
    id: str
    title: str | None
    movement: str
    tools: frozenset[str]
    sensors: frozenset[str]
    inputs: frozenset[str]
    allowed: frozenset[str]
    bounded: bool
    origin: Cell
    size: tuple[int, int]
    walls: Walls
    robot_at: Cell
    heading: str | None
    bag: int | str | None
    crystals: dict[Cell, int]
    painted: set[Cell]
    presentation: dict
    goal: Goal | None
    limits: dict[str, int]

    # --- geometry
    def inside(self, cell: Cell) -> bool:
        if not self.bounded:
            return True
        x, y = cell
        ox, oy = self.origin
        w, h = self.size
        return ox <= x < ox + w and oy <= y < oy + h

    def blocked(self, cell: Cell, direction: str) -> bool:
        """Is the edge between `cell` and its neighbour in `direction` closed?"""
        x, y = cell
        if direction == "north":
            closed = self.walls.has("h", y + 1, x)
            nxt = (x, y + 1)
        elif direction == "south":
            closed = self.walls.has("h", y, x)
            nxt = (x, y - 1)
        elif direction == "east":
            closed = self.walls.has("v", x + 1, y)
            nxt = (x + 1, y)
        else:
            closed = self.walls.has("v", x, y)
            nxt = (x - 1, y)
        return closed or not self.inside(nxt)

    def capabilities(self) -> frozenset[str]:
        return frozenset({self.movement}) | self.tools | self.sensors | self.inputs

    def normalised(self) -> dict:
        rules = {
            "movement": self.movement,
            "tools": sorted(self.tools),
            "sensors": sorted(self.sensors),
            "inputs": sorted(self.inputs),
            "allowed_commands": sorted(self.allowed),
        }
        walls = [{"axis": a, "at": at, "span": [_token(s), _token(e)]}
                 for a, at, s, e in self.walls.intervals()]
        if self.bounded:
            board = {"topology": "bounded", "origin": list(self.origin), "size": list(self.size),
                     "walls": walls}
        else:
            board = {"topology": "plane", "walls": walls}
        out = {
            "format": WORLD_FORMAT,
            "id": self.id,
            "rules": rules,
            "board": board,
            "robot": {"at": list(self.robot_at), "heading": self.heading, "bag": self.bag},
            "cells": {
                "crystals": [{"at": list(c), "count": n} for c, n in sorted_cells(self.crystals)],
                "painted": [list(c) for c in sorted(self.painted, key=lambda c: (c[1], c[0]))],
            },
            "presentation": self.presentation,
        }
        if self.title is not None:
            out["title"] = self.title
        return out


def sorted_cells(d: dict[Cell, int]) -> list[tuple[Cell, int]]:
    return sorted(d.items(), key=lambda kv: (kv[0][1], kv[0][0]))


# --------------------------------------------------------------------------- helpers

class _Ctx:
    def __init__(self, path: str | None):
        self.path = path

    def fail(self, where: str, message: str) -> MapError:
        return MapError(f"{where}: {message}" if where else message, path=self.path)


def _table(ctx: _Ctx, value: Any, where: str, allowed: Iterable[str], required: Iterable[str] = ()) -> dict:
    if not isinstance(value, dict):
        raise ctx.fail(where, "must be a table")
    allowed = set(allowed)
    for key in value:
        if key not in allowed:
            raise ctx.fail(where, f"unknown key {key!r} (allowed: {', '.join(sorted(allowed))})")
    for key in required:
        if key not in value:
            raise ctx.fail(where, f"missing required key {key!r}")
    return value


def _int(ctx: _Ctx, value: Any, where: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ctx.fail(where, "must be an integer")
    if not -SAFE <= value <= SAFE:
        raise ctx.fail(where, "is outside the exact integer range ±(2**53-1)")
    if minimum is not None and value < minimum:
        raise ctx.fail(where, f"must be at least {minimum}")
    return value


def _cell(ctx: _Ctx, value: Any, where: str) -> Cell:
    if not isinstance(value, list) or len(value) != 2:
        raise ctx.fail(where, "must be a pair [x, y]")
    return (_int(ctx, value[0], where + "[0]"), _int(ctx, value[1], where + "[1]"))


def _str(ctx: _Ctx, value: Any, where: str, choices: Iterable[str] | None = None) -> str:
    if not isinstance(value, str):
        raise ctx.fail(where, "must be a string")
    if choices is not None and value not in choices:
        raise ctx.fail(where, f"must be one of {', '.join(choices)}; got {value!r}")
    return value


def _str_list(ctx: _Ctx, value: Any, where: str, choices: Iterable[str]) -> list[str]:
    if not isinstance(value, list):
        raise ctx.fail(where, "must be a list of strings")
    choices = tuple(choices)
    seen: list[str] = []
    for i, item in enumerate(value):
        s = _str(ctx, item, f"{where}[{i}]", choices)
        if s in seen:
            raise ctx.fail(where, f"duplicate {s!r}")
        seen.append(s)
    return seen


def _bool(ctx: _Ctx, value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise ctx.fail(where, "must be true or false")
    return value


def _endpoint(ctx: _Ctx, value: Any, where: str, plane: bool) -> float:
    if isinstance(value, str):
        if not plane:
            raise ctx.fail(where, "infinite wall ends are allowed only on a plane board")
        if value == "-inf":
            return NEG_INF
        if value == "+inf":
            return POS_INF
        raise ctx.fail(where, 'must be an integer, "-inf" or "+inf"')
    return _int(ctx, value, where)


def _load_toml(data: bytes | str, ctx: _Ctx, max_bytes: int) -> dict:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if len(raw) > max_bytes:
        raise MapError(f"document is larger than {max_bytes} bytes", path=ctx.path)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        raise MapError(f"not valid UTF-8 at byte {e.start}", path=ctx.path) from None
    if text.startswith("﻿"):
        text = text[1:]
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise MapError(f"TOML syntax error: {e}", path=ctx.path,
                       line=getattr(e, "lineno", None), column=getattr(e, "colno", None)) from None


# --------------------------------------------------------------------------- ASCII

def parse_ascii(ctx: _Ctx, text: str, origin: Cell) -> tuple[tuple[int, int], list[tuple[str, int, float, float]]]:
    if "\t" in text:
        raise ctx.fail("board.ascii", "tabs are not allowed")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        raise ctx.fail("board.ascii", "is empty")
    indent = min(len(l) - len(l.lstrip(" ")) for l in lines if l.strip())
    lines = [l[indent:].rstrip(" ") for l in lines]
    width_chars = len(lines[0])
    if width_chars < 5 or (width_chars - 1) % 4:
        raise ctx.fail("board.ascii", f"line 1 has {width_chars} characters; a W-cell board needs 4W+1")
    if len(lines) < 3 or len(lines) % 2 == 0:
        raise ctx.fail("board.ascii", f"has {len(lines)} lines; an H-cell board needs 2H+1")
    w = (width_chars - 1) // 4
    h = (len(lines) - 1) // 2
    ox, oy = origin
    walls: list[tuple[str, int, float, float]] = []

    def where(i: int, j: int) -> str:
        return f"board.ascii line {i + 1}, column {j + 1}"

    for i, line in enumerate(lines):
        if len(line) != width_chars:
            raise ctx.fail(f"board.ascii line {i + 1}", f"has {len(line)} characters, expected {width_chars}")
        if i % 2 == 0:  # junction row: horizontal edges of line y
            y = oy + h - i // 2
            for k in range(w + 1):
                if line[4 * k] != "+":
                    raise ctx.fail(where(i, 4 * k), f"expected '+', found {line[4 * k]!r}")
            for k in range(w):
                seg = line[4 * k + 1:4 * k + 4]
                if seg == "---":
                    walls.append(("h", y, ox + k, ox + k + 1))
                elif seg != "   ":
                    raise ctx.fail(where(i, 4 * k + 1), f"expected '---' or three spaces, found {seg!r}")
                elif i in (0, 2 * h):
                    raise ctx.fail(where(i, 4 * k + 1), "the outer contour must be closed")
        else:  # cell row: vertical edges, x lines
            y = oy + h - 1 - i // 2
            for k in range(w + 1):
                c = line[4 * k]
                if c == "|":
                    walls.append(("v", ox + k, y, y + 1))
                elif c != " ":
                    raise ctx.fail(where(i, 4 * k), f"expected '|' or a space, found {c!r}")
                elif k in (0, w):
                    raise ctx.fail(where(i, 4 * k), "the outer contour must be closed")
            for k in range(w):
                seg = line[4 * k + 1:4 * k + 4]
                if seg != " . ":
                    raise ctx.fail(where(i, 4 * k + 1), f"a cell must be ' . ', found {seg!r}")
    return (w, h), walls


# --------------------------------------------------------------------------- world

def loads_world(data: bytes | str, *, path: str | None = None, max_bytes: int = MAX_MAP_BYTES) -> World:
    ctx = _Ctx(path)
    doc = _load_toml(data, ctx, max_bytes)
    return world_from_dict(doc, path=path)


def load_world(source: str | Path | BinaryIO, *, max_bytes: int = MAX_MAP_BYTES) -> World:
    if hasattr(source, "read"):
        data = source.read(max_bytes + 1)
        return loads_world(data, path=getattr(source, "name", None), max_bytes=max_bytes)
    p = Path(source)
    with p.open("rb") as fh:
        data = fh.read(max_bytes + 1)
    return loads_world(data, path=str(p), max_bytes=max_bytes)


def world_from_dict(doc: dict, *, path: str | None = None) -> World:
    ctx = _Ctx(path)
    _table(ctx, doc, "", ("format", "id", "title", "rules", "board", "robot", "cells",
                          "presentation", "goal", "limits"), ("format", "id", "rules", "board", "robot"))
    if doc["format"] != WORLD_FORMAT:
        raise ctx.fail("format", f"must be {WORLD_FORMAT!r}")
    wid = _str(ctx, doc["id"], "id")
    if not _ID.fullmatch(wid):
        raise ctx.fail("id", "must be 1–128 characters: letters, digits, '_', '.', '-'")
    title = _str(ctx, doc["title"], "title") if "title" in doc else None

    # rules
    rules = _table(ctx, doc["rules"], "rules", ("movement", "tools", "sensors", "inputs", "allowed_commands"),
                   ("movement",))
    movement = _str(ctx, rules["movement"], "rules.movement", catalog.MOVEMENTS)
    tools = frozenset(_str_list(ctx, rules.get("tools", []), "rules.tools", catalog.TOOLS))
    sensors = frozenset(_str_list(ctx, rules.get("sensors", []), "rules.sensors", catalog.SENSORS))
    inputs = frozenset(_str_list(ctx, rules.get("inputs", []), "rules.inputs", catalog.INPUTS))
    if "eraser" in tools and "paint" not in tools:
        raise ctx.fail("rules.tools", "'eraser' requires 'paint'")
    if "compass" in sensors and movement != "relative":
        raise ctx.fail("rules.sensors", "'compass' requires relative movement")
    if "counts" in sensors and "crystals" not in tools:
        raise ctx.fail("rules.sensors", "'counts' requires the 'crystals' tool")
    if inputs:
        raise ctx.fail("rules.inputs", "keyboard and pointer input are not available in this release")
    caps = frozenset({movement}) | tools | sensors | inputs
    permitted = {f.name for f in catalog.FUNCTIONS if set(f.requires) <= caps}
    if "allowed_commands" in rules:
        listed = _str_list(ctx, rules["allowed_commands"], "rules.allowed_commands", catalog.NAMES)
        allowed = frozenset(listed) & permitted
    else:
        allowed = frozenset(permitted)

    # board
    board = doc["board"]
    if not isinstance(board, dict):
        raise ctx.fail("board", "must be a table")
    topology = _str(ctx, board.get("topology", "bounded"), "board.topology", ("bounded", "plane"))
    plane = topology == "plane"
    if plane:
        _table(ctx, board, "board", ("topology", "walls"))
        origin, size = (0, 0), (0, 0)
        raw_walls: list[tuple[str, int, float, float]] = []
    else:
        _table(ctx, board, "board", ("topology", "origin", "size", "walls", "ascii"))
        origin = _cell(ctx, board["origin"], "board.origin") if "origin" in board else (0, 0)
        if "ascii" in board:
            if "size" in board or "walls" in board:
                raise ctx.fail("board", "'ascii' replaces 'size' and 'walls'; do not combine them")
            size, raw_walls = parse_ascii(ctx, _str(ctx, board["ascii"], "board.ascii"), origin)
        else:
            if "size" not in board:
                raise ctx.fail("board", "a bounded board needs 'size' or 'ascii'")
            sz = board["size"]
            if not isinstance(sz, list) or len(sz) != 2:
                raise ctx.fail("board.size", "must be [width, height]")
            size = (_int(ctx, sz[0], "board.size[0]", minimum=1), _int(ctx, sz[1], "board.size[1]", minimum=1))
            raw_walls = []
        if size[0] > MAX_BOARD_SIDE or size[1] > MAX_BOARD_SIDE:
            raise ctx.fail("board.size", f"sides are limited to {MAX_BOARD_SIDE}")
        for i, v in enumerate(origin):
            if not -SAFE <= v + size[i] <= SAFE:
                raise ctx.fail("board", "board extends beyond the exact integer range")
    walls_src = board.get("walls", [])
    if not isinstance(walls_src, list):
        raise ctx.fail("board.walls", "must be a list")
    if len(walls_src) > MAX_WALLS:
        raise ctx.fail("board.walls", f"at most {MAX_WALLS} walls")
    pieces: list[tuple[str, int, float, float]] = list(raw_walls)
    for i, w in enumerate(walls_src):
        wh = f"board.walls[{i}]"
        _table(ctx, w, wh, ("axis", "at", "span", "gaps"), ("axis", "at", "span"))
        axis = _str(ctx, w["axis"], wh + ".axis", ("h", "v"))
        at = _int(ctx, w["at"], wh + ".at")
        sp = w["span"]
        if not isinstance(sp, list) or len(sp) != 2:
            raise ctx.fail(wh + ".span", "must be [a, b]")
        a = _endpoint(ctx, sp[0], wh + ".span[0]", plane)
        b = _endpoint(ctx, sp[1], wh + ".span[1]", plane)
        if a == POS_INF or b == NEG_INF:
            raise ctx.fail(wh + ".span", 'use "-inf" for the lower end and "+inf" for the upper end')
        if not a < b:
            raise ctx.fail(wh + ".span", "needs a < b")
        gaps = []
        for j, g in enumerate(w.get("gaps", [])):
            gw = f"{wh}.gaps[{j}]"
            if not isinstance(g, list) or len(g) != 2:
                raise ctx.fail(gw, "must be [a, b]")
            ga, gb = _int(ctx, g[0], gw + "[0]"), _int(ctx, g[1], gw + "[1]")
            if not (a <= ga < gb <= b):
                raise ctx.fail(gw, "must be a non-empty interval inside the wall's span")
            gaps.append((ga, gb))
        if "gaps" in w and not isinstance(w["gaps"], list):
            raise ctx.fail(wh + ".gaps", "must be a list")
        segs = [(a, b)]
        for ga, gb in sorted(gaps):
            nxt = []
            for s, e in segs:
                if gb <= s or ga >= e:
                    nxt.append((s, e))
                    continue
                if s < ga:
                    nxt.append((s, ga))
                if gb < e:
                    nxt.append((gb, e))
            segs = nxt
        if not plane:
            ox, oy = origin
            wd, ht = size
            lo, hi = (oy, oy + ht) if axis == "h" else (ox, ox + wd)
            slo, shi = (ox, ox + wd) if axis == "h" else (oy, oy + ht)
            if not (lo <= at <= hi and slo <= a and b <= shi):
                raise ctx.fail(wh, "lies outside the board")
        pieces.extend((axis, at, s, e) for s, e in segs)
    if not plane:
        ox, oy = origin
        wd, ht = size
        outer = {("h", oy), ("h", oy + ht), ("v", ox), ("v", ox + wd)}
        pieces = [p for p in pieces if (p[0], p[1]) not in outer]
    walls = Walls.from_intervals(pieces)

    def inside(c: Cell) -> bool:
        if plane:
            return True
        return origin[0] <= c[0] < origin[0] + size[0] and origin[1] <= c[1] < origin[1] + size[1]

    # robot
    robot = _table(ctx, doc["robot"], "robot", ("at", "heading", "bag"), ("at",))
    at = _cell(ctx, robot["at"], "robot.at")
    if not inside(at):
        raise ctx.fail("robot.at", "is outside the board")
    if movement == "relative":
        if "heading" not in robot:
            raise ctx.fail("robot", "relative movement needs 'heading'")
        heading = _str(ctx, robot["heading"], "robot.heading", HEADINGS)
    else:
        if "heading" in robot:
            raise ctx.fail("robot.heading", "an absolute robot has no heading")
        heading = None
    if "crystals" in tools:
        if "bag" not in robot:
            raise ctx.fail("robot", "with crystals enabled 'bag' is required (a count or \"infinite\")")
        bag = robot["bag"]
        if bag != "infinite":
            bag = _int(ctx, bag, "robot.bag", minimum=0)
    else:
        if "bag" in robot:
            raise ctx.fail("robot.bag", "needs the 'crystals' tool")
        bag = None

    # cells
    crystals: dict[Cell, int] = {}
    painted: set[Cell] = set()
    if "cells" in doc:
        cells = _table(ctx, doc["cells"], "cells", ("crystals", "painted"))
        if "crystals" in cells:
            if "crystals" not in tools:
                raise ctx.fail("cells.crystals", "needs the 'crystals' tool")
            if not isinstance(cells["crystals"], list):
                raise ctx.fail("cells.crystals", "must be a list")
            for i, item in enumerate(cells["crystals"]):
                wh = f"cells.crystals[{i}]"
                _table(ctx, item, wh, ("at", "count"), ("at", "count"))
                c = _cell(ctx, item["at"], wh + ".at")
                n = _int(ctx, item["count"], wh + ".count", minimum=1)
                if c in crystals:
                    raise ctx.fail(wh, f"duplicate cell {list(c)}")
                if not inside(c):
                    raise ctx.fail(wh, "is outside the board")
                crystals[c] = n
        if "painted" in cells:
            if "paint" not in tools:
                raise ctx.fail("cells.painted", "needs the 'paint' tool")
            if not isinstance(cells["painted"], list):
                raise ctx.fail("cells.painted", "must be a list")
            for i, item in enumerate(cells["painted"]):
                c = _cell(ctx, item, f"cells.painted[{i}]")
                if c in painted:
                    raise ctx.fail(f"cells.painted[{i}]", f"duplicate cell {list(c)}")
                if not inside(c):
                    raise ctx.fail(f"cells.painted[{i}]", "is outside the board")
                painted.add(c)

    # presentation
    pres_out: dict = {"theme": "workshop", "show_coordinates": False, "markers": []}
    if "presentation" in doc:
        pres = _table(ctx, doc["presentation"], "presentation",
                      ("theme", "show_coordinates", "viewport", "markers"))
        if "theme" in pres:
            pres_out["theme"] = _str(ctx, pres["theme"], "presentation.theme", ("workshop",))
        if "show_coordinates" in pres:
            pres_out["show_coordinates"] = _bool(ctx, pres["show_coordinates"], "presentation.show_coordinates")
        if "viewport" in pres:
            vp = pres["viewport"]
            if not isinstance(vp, list) or len(vp) != 4:
                raise ctx.fail("presentation.viewport", "must be [xmin, ymin, width, height]")
            vals = [_int(ctx, v, f"presentation.viewport[{i}]") for i, v in enumerate(vp)]
            if vals[2] < 1 or vals[3] < 1:
                raise ctx.fail("presentation.viewport", "width and height must be positive")
            pres_out["viewport"] = vals
        if "markers" in pres:
            if not isinstance(pres["markers"], list):
                raise ctx.fail("presentation.markers", "must be a list")
            seen = set()
            for i, m in enumerate(pres["markers"]):
                wh = f"presentation.markers[{i}]"
                _table(ctx, m, wh, ("at", "kind"), ("at", "kind"))
                c = _cell(ctx, m["at"], wh + ".at")
                kind = _str(ctx, m["kind"], wh + ".kind", MARKER_KINDS)
                if (c, kind) in seen:
                    raise ctx.fail(wh, "duplicate marker")
                if not inside(c):
                    raise ctx.fail(wh, "is outside the board")
                seen.add((c, kind))
            pres_out["markers"] = [{"at": list(c), "kind": k} for c, k in
                                   sorted(seen, key=lambda ck: (ck[0][1], ck[0][0], ck[1]))]
    if plane and "viewport" not in pres_out:
        pres_out["viewport"] = _default_viewport(at, crystals, painted, walls)

    # limits
    limits: dict[str, int] = {}
    if "limits" in doc:
        lim = _table(ctx, doc["limits"], "limits", LIMIT_KEYS)
        for k, v in lim.items():
            limits[k] = _int(ctx, v, f"limits.{k}", minimum=0)

    world = World(id=wid, title=title, movement=movement, tools=tools, sensors=sensors, inputs=inputs,
                  allowed=allowed, bounded=not plane, origin=origin, size=size, walls=walls,
                  robot_at=at, heading=heading, bag=bag, crystals=crystals, painted=painted,
                  presentation=pres_out, goal=None, limits=limits)
    if "goal" in doc:
        world.goal = goal_from_table(doc["goal"], world, ctx, "goal")
    return world


def _default_viewport(at: Cell, crystals, painted, walls: Walls) -> list[int]:
    xs = [at[0]] + [c[0] for c in crystals] + [c[0] for c in painted]
    ys = [at[1]] + [c[1] for c in crystals] + [c[1] for c in painted]
    for axis, line, a, b in walls.intervals():
        finite = [v for v in (a, b) if math.isfinite(v)]
        if axis == "h":
            ys.append(line)
            xs.extend(int(v) for v in finite)
        else:
            xs.append(line)
            ys.extend(int(v) for v in finite)
    x0, x1 = min(xs) - 2, max(xs) + 3
    y0, y1 = min(ys) - 2, max(ys) + 3
    return [x0, y0, max(x1 - x0, 8), max(y1 - y0, 6)]


# --------------------------------------------------------------------------- goals

def goal_from_table(tbl: Any, world: World, ctx: _Ctx, where: str) -> Goal:
    _table(ctx, tbl, where, ("robot_at", "robot_heading", "bag", "crystals", "paint", "visits"))
    g = Goal()
    if "robot_at" in tbl:
        g.robot_at = _cell(ctx, tbl["robot_at"], f"{where}.robot_at")
    if "robot_heading" in tbl:
        if world.movement != "relative":
            raise ctx.fail(f"{where}.robot_heading", "only for relative movement")
        g.robot_heading = _str(ctx, tbl["robot_heading"], f"{where}.robot_heading", HEADINGS)
    if "bag" in tbl:
        if "crystals" not in world.tools:
            raise ctx.fail(f"{where}.bag", "needs the 'crystals' tool")
        g.has_bag = True
        g.bag = "infinite" if tbl["bag"] == "infinite" else _int(ctx, tbl["bag"], f"{where}.bag", minimum=0)
    if "crystals" in tbl:
        if "crystals" not in world.tools:
            raise ctx.fail(f"{where}.crystals", "needs the 'crystals' tool")
        t = _table(ctx, tbl["crystals"], f"{where}.crystals", ("mode", "cells"), ("mode",))
        g.crystals_mode = _str(ctx, t["mode"], f"{where}.crystals.mode", ("exact", "specified", "unchanged"))
        if g.crystals_mode == "unchanged":
            if "cells" in t:
                raise ctx.fail(f"{where}.crystals", "'unchanged' takes no cells")
        else:
            if "cells" not in t or not isinstance(t["cells"], list):
                raise ctx.fail(f"{where}.crystals.cells", "must be a list")
            for i, item in enumerate(t["cells"]):
                wh = f"{where}.crystals.cells[{i}]"
                _table(ctx, item, wh, ("at", "count"), ("at", "count"))
                c = _cell(ctx, item["at"], wh + ".at")
                n = _int(ctx, item["count"], wh + ".count", minimum=1 if g.crystals_mode == "exact" else 0)
                if c in g.crystals:
                    raise ctx.fail(wh, "duplicate cell")
                g.crystals[c] = n
    if "paint" in tbl:
        if "paint" not in world.tools:
            raise ctx.fail(f"{where}.paint", "needs the 'paint' tool")
        t = _table(ctx, tbl["paint"], f"{where}.paint", ("mode", "cells"), ("mode",))
        g.paint_mode = _str(ctx, t["mode"], f"{where}.paint.mode", ("exact", "contains", "unchanged"))
        if g.paint_mode == "unchanged":
            if "cells" in t:
                raise ctx.fail(f"{where}.paint", "'unchanged' takes no cells")
        else:
            g.paint = _cell_set(ctx, t.get("cells"), f"{where}.paint.cells")
    if "visits" in tbl:
        t = _table(ctx, tbl["visits"], f"{where}.visits", ("mode", "cells", "forbid_revisits"))
        if "mode" in t:
            g.visits_mode = _str(ctx, t["mode"], f"{where}.visits.mode", ("contains", "exact", "all_reachable"))
            if g.visits_mode == "all_reachable":
                if "cells" in t:
                    raise ctx.fail(f"{where}.visits", "'all_reachable' takes no cells")
            else:
                g.visits = _cell_set(ctx, t.get("cells"), f"{where}.visits.cells")
        elif "cells" in t:
            raise ctx.fail(f"{where}.visits", "'cells' needs a 'mode'")
        if "forbid_revisits" in t:
            g.forbid_revisits = _bool(ctx, t["forbid_revisits"], f"{where}.visits.forbid_revisits")
    return g


def _cell_set(ctx: _Ctx, value: Any, where: str) -> set[Cell]:
    if not isinstance(value, list):
        raise ctx.fail(where, "must be a list of [x, y] pairs")
    out: set[Cell] = set()
    for i, item in enumerate(value):
        c = _cell(ctx, item, f"{where}[{i}]")
        if c in out:
            raise ctx.fail(f"{where}[{i}]", "duplicate cell")
        out.add(c)
    return out


def loads_goal(data: bytes | str, world: World, *, path: str | None = None) -> Goal:
    ctx = _Ctx(path)
    doc = _load_toml(data, ctx, MAX_MAP_BYTES)
    _table(ctx, doc, "", ("format", "goal"), ("format", "goal"))
    if doc["format"] != GOAL_FORMAT:
        raise ctx.fail("format", f"must be {GOAL_FORMAT!r}")
    return goal_from_table(doc["goal"], world, ctx, "goal")


def load_goal(path: str | Path, world: World) -> Goal:
    p = Path(path)
    return loads_goal(p.read_bytes(), world, path=str(p))
