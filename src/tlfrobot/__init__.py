"""tlfrobot — a grid robot for learning Python.

    from tlfrobot import *

Run a program with `python -m tlfrobot run solution.py` (a `map.toml` next to it),
or in the course portal. Which functions work depends on the world: see each
function's "Needs" line.
"""
# Generated from catalog.py by tools/gen_init.py; edit the catalogue, not this file.
from __future__ import annotations

import os as _os

from . import runtime as _runtime
from ._version import __version__

__all__ = [
    "move",
    "turn_left",
    "turn_right",
    "turn_around",
    "front_clear",
    "left_clear",
    "right_clear",
    "back_clear",
    "north",
    "south",
    "east",
    "west",
    "north_clear",
    "south_clear",
    "east_clear",
    "west_clear",
    "take",
    "put",
    "on_crystal",
    "bag_empty",
    "paint",
    "painted",
    "erase",
    "facing_north",
    "facing_south",
    "facing_east",
    "facing_west",
    "crystal_count",
    "bag_count",
]


def move() -> None:
    """Move forward by one cell.

    Needs: relative."""
    return _runtime.call("move")


def turn_left() -> None:
    """Turn 90° to the left on the spot.

    Needs: relative."""
    return _runtime.call("turn_left")


def turn_right() -> None:
    """Turn 90° to the right on the spot.

    Needs: relative."""
    return _runtime.call("turn_right")


def turn_around() -> None:
    """Turn around (180°) on the spot.

    Needs: relative."""
    return _runtime.call("turn_around")


def front_clear() -> bool:
    """True if there is no wall in front.

    Needs: relative."""
    return _runtime.call("front_clear")


def left_clear() -> bool:
    """True if there is no wall on the left.

    Needs: relative."""
    return _runtime.call("left_clear")


def right_clear() -> bool:
    """True if there is no wall on the right.

    Needs: relative."""
    return _runtime.call("right_clear")


def back_clear() -> bool:
    """True if there is no wall behind.

    Needs: relative."""
    return _runtime.call("back_clear")


def north() -> None:
    """Step one cell north (up).

    Needs: absolute."""
    return _runtime.call("north")


def south() -> None:
    """Step one cell south (down).

    Needs: absolute."""
    return _runtime.call("south")


def east() -> None:
    """Step one cell east (right).

    Needs: absolute."""
    return _runtime.call("east")


def west() -> None:
    """Step one cell west (left).

    Needs: absolute."""
    return _runtime.call("west")


def north_clear() -> bool:
    """True if there is no wall to the north.

    Needs: absolute."""
    return _runtime.call("north_clear")


def south_clear() -> bool:
    """True if there is no wall to the south.

    Needs: absolute."""
    return _runtime.call("south_clear")


def east_clear() -> bool:
    """True if there is no wall to the east.

    Needs: absolute."""
    return _runtime.call("east_clear")


def west_clear() -> bool:
    """True if there is no wall to the west.

    Needs: absolute."""
    return _runtime.call("west_clear")


def take() -> None:
    """Pick up one crystal from this cell into the bag.

    Needs: crystals."""
    return _runtime.call("take")


def put() -> None:
    """Put one crystal from the bag onto this cell.

    Needs: crystals."""
    return _runtime.call("put")


def on_crystal() -> bool:
    """True if this cell has at least one crystal.

    Needs: crystals."""
    return _runtime.call("on_crystal")


def bag_empty() -> bool:
    """True if the bag has no crystals (never for an infinite bag).

    Needs: crystals."""
    return _runtime.call("bag_empty")


def paint() -> None:
    """Paint this cell.

    Needs: paint."""
    return _runtime.call("paint")


def painted() -> bool:
    """True if this cell is painted.

    Needs: paint."""
    return _runtime.call("painted")


def erase() -> None:
    """Remove the paint from this cell.

    Needs: paint, eraser."""
    return _runtime.call("erase")


def facing_north() -> bool:
    """True if the robot faces north.

    Needs: relative, compass."""
    return _runtime.call("facing_north")


def facing_south() -> bool:
    """True if the robot faces south.

    Needs: relative, compass."""
    return _runtime.call("facing_south")


def facing_east() -> bool:
    """True if the robot faces east.

    Needs: relative, compass."""
    return _runtime.call("facing_east")


def facing_west() -> bool:
    """True if the robot faces west.

    Needs: relative, compass."""
    return _runtime.call("facing_west")


def crystal_count() -> int:
    """How many crystals lie on this cell.

    Needs: crystals, counts."""
    return _runtime.call("crystal_count")


def bag_count() -> int | None:
    """How many crystals are in the bag (None if it is infinite).

    Needs: crystals, counts."""
    return _runtime.call("bag_count")


if _os.environ.get("TLFROBOT_MODE") == "ejudge" and _runtime._current is None:
    _runtime.start_ejudge_auto()
