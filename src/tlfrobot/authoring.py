"""Writing worlds and goals from Python, for task generators.

    from tlfrobot.authoring import Board
    b = Board(5, 3, robot=(0, 0), heading="east", bag=0, tools=["crystals"])
    b.wall_h(1, 1, 3)          # the line y=1 from x=1 to x=3
    b.crystal(2, 0, 3)
    b.finish(4, 2)
    text = b.toml(id="b2-world-1")

Everything is validated by parsing the result with `maps.loads_world`, so a
generator cannot write a world the runtime would refuse.
"""
from __future__ import annotations

import json
from typing import Iterable

from . import maps
from .core import State
from .maps import Cell


def _q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _cells(cells: Iterable[Cell]) -> str:
    return "[" + ", ".join(f"[{x}, {y}]" for x, y in sorted(cells, key=lambda c: (c[1], c[0]))) + "]"


class Board:
    def __init__(self, width: int, height: int, *, robot: Cell = (0, 0), heading: str | None = "east",
                 bag: int | str | None = 0, movement: str = "relative", tools: Iterable[str] = ("crystals",),
                 sensors: Iterable[str] = (), allowed: Iterable[str] | None = None, title: str | None = None):
        self.width, self.height = width, height
        self.robot = tuple(robot)
        self.movement = movement
        self.heading = heading if movement == "relative" else None
        self.tools = list(tools)
        self.sensors = list(sensors)
        self.allowed = list(allowed) if allowed is not None else None
        self.bag = bag if "crystals" in self.tools else None
        self.title = title
        self.walls: list[tuple[str, int, int, int]] = []
        self.crystals: dict[Cell, int] = {}
        self.painted: set[Cell] = set()
        self.markers: list[tuple[Cell, str]] = []

    # walls: a run of unit edges on one grid line
    def wall_h(self, y: int, x0: int, x1: int) -> "Board":
        """Horizontal wall on the line between rows y-1 and y, from x0 to x1."""
        self.walls.append(("h", y, x0, x1))
        return self

    def wall_v(self, x: int, y0: int, y1: int) -> "Board":
        """Vertical wall on the line between columns x-1 and x, from y0 to y1."""
        self.walls.append(("v", x, y0, y1))
        return self

    def wall_north(self, x: int, y: int) -> "Board":
        return self.wall_h(y + 1, x, x + 1)

    def wall_east(self, x: int, y: int) -> "Board":
        return self.wall_v(x + 1, y, y + 1)

    def crystal(self, x: int, y: int, count: int = 1) -> "Board":
        if count > 0:
            self.crystals[(x, y)] = self.crystals.get((x, y), 0) + count
        return self

    def paint(self, x: int, y: int) -> "Board":
        self.painted.add((x, y))
        return self

    def finish(self, x: int, y: int) -> "Board":
        self.markers.append(((x, y), "finish"))
        return self

    def target(self, x: int, y: int) -> "Board":
        self.markers.append(((x, y), "target"))
        return self

    def start(self, x: int, y: int) -> "Board":
        self.markers.append(((x, y), "start"))
        return self

    def toml(self, *, id: str, goal: str | None = None) -> str:
        out = ['format = "tlfrobot-world/1"', f"id = {_q(id)}"]
        if self.title:
            out.append(f"title = {_q(self.title)}")
        out += ["", "[rules]", f"movement = {_q(self.movement)}"]
        if self.tools:
            out.append("tools = [" + ", ".join(_q(t) for t in self.tools) + "]")
        if self.sensors:
            out.append("sensors = [" + ", ".join(_q(s) for s in self.sensors) + "]")
        if self.allowed is not None:
            out.append("allowed_commands = [" + ", ".join(_q(a) for a in self.allowed) + "]")
        out += ["", "[board]", f"size = [{self.width}, {self.height}]"]
        if self.walls:
            out.append("walls = [")
            for axis, at, a, b in self.walls:
                out.append(f'    {{ axis = "{axis}", at = {at}, span = [{a}, {b}] }},')
            out.append("]")
        out += ["", "[robot]", f"at = [{self.robot[0]}, {self.robot[1]}]"]
        if self.heading is not None:
            out.append(f"heading = {_q(self.heading)}")
        if self.bag is not None:
            out.append(f"bag = {_q(self.bag) if isinstance(self.bag, str) else self.bag}")
        if self.crystals or self.painted:
            out += ["", "[cells]"]
            if self.crystals:
                items = sorted(self.crystals.items(), key=lambda kv: (kv[0][1], kv[0][0]))
                out.append("crystals = [" + ", ".join(f"{{ at = [{x}, {y}], count = {n} }}" for (x, y), n in items) + "]")
            if self.painted:
                out.append(f"painted = {_cells(self.painted)}")
        if self.markers:
            out += ["", "[presentation]", "markers = ["]
            for (x, y), kind in sorted(self.markers, key=lambda m: (m[0][1], m[0][0], m[1])):
                out.append(f'    {{ at = [{x}, {y}], kind = "{kind}" }},')
            out.append("]")
        if goal:
            out += ["", goal.strip()]
        text = "\n".join(out) + "\n"
        maps.loads_world(text)  # never write a world the runtime would refuse
        return text


GOAL_PARTS = ("robot_at", "robot_heading", "bag", "crystals", "paint")


def goal_from_state(world: maps.World, state: State, parts: Iterable[str], *, embedded: bool = False) -> str:
    """A goal that holds exactly for `state`, restricted to `parts`."""
    parts = list(parts)
    for p in parts:
        if p not in GOAL_PARTS:
            raise ValueError(f"unknown goal part {p!r} (choose from {', '.join(GOAL_PARTS)})")
    lines = [] if embedded else ['format = "tlfrobot-goal/1"', ""]
    lines.append("[goal]")
    if "robot_at" in parts:
        lines.append(f"robot_at = [{state.at[0]}, {state.at[1]}]")
    if "robot_heading" in parts and state.heading is not None:
        lines.append(f"robot_heading = {_q(state.heading)}")
    if "bag" in parts and state.bag is not None:
        lines.append(f"bag = {_q(state.bag) if isinstance(state.bag, str) else state.bag}")
    if "crystals" in parts:
        items = sorted(state.crystals.items(), key=lambda kv: (kv[0][1], kv[0][0]))
        lines += ["", "[goal.crystals]", 'mode = "exact"',
                  "cells = [" + ", ".join(f"{{ at = [{x}, {y}], count = {n} }}" for (x, y), n in items) + "]"]
    if "paint" in parts:
        lines += ["", "[goal.paint]", 'mode = "exact"', f"cells = {_cells(state.painted)}"]
    text = "\n".join(lines) + "\n"
    if not embedded:
        maps.loads_goal(text, world)
    return text
