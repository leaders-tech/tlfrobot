"""The physical rules, in one place. Every runtime and the checker use this.

`prepare(world, state, op)` never changes anything: it returns a Transaction
with the sampled result, the state after a successful commit (or None when
nothing changes) and `fx`, the facts a renderer needs to animate the call.
A world error is returned as a Transaction with `error` set, so a host can
show the failed attempt before the error is raised.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from . import catalog
from .errors import (CommandUnavailableError, EmptyBagError, NoCrystalError, NumberRangeError,
                     RobotError, WallCollisionError)
from .maps import SAFE, Cell, World, sorted_cells

HEADINGS = ("north", "east", "south", "west")
STEP = {"north": (0, 1), "east": (1, 0), "south": (0, -1), "west": (-1, 0)}
TURN = {"turn_left": -1, "turn_right": 1, "turn_around": 2}
RELATIVE_SENSOR = {"front_clear": 0, "right_clear": 1, "back_clear": 2, "left_clear": 3}
ABSOLUTE_MOVE = {"north": "north", "south": "south", "east": "east", "west": "west"}
ABSOLUTE_SENSOR = {"north_clear": "north", "south_clear": "south", "east_clear": "east",
                   "west_clear": "west"}
FACING = {"facing_north": "north", "facing_south": "south", "facing_east": "east",
          "facing_west": "west"}


@dataclass
class State:
    at: Cell
    heading: str | None
    bag: int | str | None
    crystals: dict[Cell, int]
    painted: set[Cell]
    time_us: int = 0
    rev: int = 0

    @classmethod
    def initial(cls, world: World) -> "State":
        return cls(world.robot_at, world.heading, world.bag, dict(world.crystals), set(world.painted))

    def copy(self) -> "State":
        return replace(self, crystals=dict(self.crystals), painted=set(self.painted))

    def compact(self) -> dict:
        """The trace's final-state form."""
        return {
            "robot": {"at": list(self.at), "heading": self.heading, "bag": self.bag},
            "crystals": [[c[0], c[1], n] for c, n in sorted_cells(self.crystals)],
            "painted": [list(c) for c in sorted(self.painted, key=lambda c: (c[1], c[0]))],
            "time_us": self.time_us,
        }

    def state_cells(self) -> int:
        return len(set(self.crystals) | self.painted)


@dataclass
class Transaction:
    op: str
    kind: str  # action | sensor
    result: Any = None
    after: State | None = None  # None: no physical change
    error: RobotError | None = None
    fx: dict = field(default_factory=dict)

    @property
    def changes(self) -> bool:
        return self.after is not None


def turn(heading: str, quarter: int) -> str:
    return HEADINGS[(HEADINGS.index(heading) + quarter) % 4]


def _check_range(cell: Cell) -> None:
    if not all(-SAFE <= v <= SAFE for v in cell):
        raise NumberRangeError("the robot would leave the exact integer coordinate range", at=list(cell))


def check_available(world: World, op: str) -> None:
    fn = catalog.BY_NAME.get(op)
    if fn is None:
        raise CommandUnavailableError(f"{op}() is not a robot command")
    if op not in world.allowed:
        missing = [r for r in fn.requires if r not in world.capabilities()]
        if missing:
            why = f"this world does not have: {', '.join(missing)}"
        else:
            why = "this task does not allow it"
        raise CommandUnavailableError(f"{op}() is not available here ({why})", op=op, missing=missing)


def prepare(world: World, state: State, op: str) -> Transaction:
    """Check and prepare `op`. Raises CommandUnavailableError (nothing to show);
    world errors come back inside the Transaction."""
    check_available(world, op)
    fn = catalog.BY_NAME[op]
    at = state.at
    tx = Transaction(op, fn.kind)

    def move_to(direction: str) -> Transaction:
        tx.fx = {"from": list(at), "dir": direction}
        if world.blocked(at, direction):
            tx.error = WallCollisionError(f"{op}(): there is a wall to the {direction}",
                                          at=list(at), dir=direction)
            return tx
        dx, dy = STEP[direction]
        nxt = (at[0] + dx, at[1] + dy)
        _check_range(nxt)
        after = state.copy()
        after.at = nxt
        after.rev += 1
        tx.after = after
        tx.fx["to"] = list(nxt)
        return tx

    if op == "move":
        return move_to(state.heading)
    if op in ABSOLUTE_MOVE:
        return move_to(ABSOLUTE_MOVE[op])
    if op in TURN:
        q = TURN[op]
        after = state.copy()
        after.heading = turn(state.heading, q)
        after.rev += 1
        tx.after = after
        tx.fx = {"from": state.heading, "to": after.heading, "angle": 90 * q if q != 2 else 180}
        return tx
    if op in RELATIVE_SENSOR:
        direction = turn(state.heading, RELATIVE_SENSOR[op])
        tx.result = not world.blocked(at, direction)
        tx.fx = {"dir": direction, "at": list(at)}
        return tx
    if op in ABSOLUTE_SENSOR:
        direction = ABSOLUTE_SENSOR[op]
        tx.result = not world.blocked(at, direction)
        tx.fx = {"dir": direction, "at": list(at)}
        return tx
    if op in FACING:
        tx.result = state.heading == FACING[op]
        tx.fx = {"query": FACING[op], "heading": state.heading}
        return tx

    here = state.crystals.get(at, 0)
    if op == "take":
        tx.fx = {"cell": list(at), "cell_before": here, "bag_before": state.bag}
        if here == 0:
            tx.error = NoCrystalError("take(): there is no crystal on this cell", at=list(at))
            tx.fx["target"] = "cell"
            return tx
        after = state.copy()
        if here == 1:
            del after.crystals[at]
        else:
            after.crystals[at] = here - 1
        if after.bag != "infinite":
            if after.bag + 1 > SAFE:
                raise NumberRangeError("the bag count would exceed the exact integer range")
            after.bag += 1
        after.rev += 1
        tx.after = after
        tx.fx.update(cell_after=here - 1, bag_after=after.bag)
        return tx
    if op == "put":
        tx.fx = {"cell": list(at), "cell_before": here, "bag_before": state.bag}
        if state.bag != "infinite" and state.bag == 0:
            tx.error = EmptyBagError("put(): the bag is empty", at=list(at))
            tx.fx["target"] = "bag"
            return tx
        if here + 1 > SAFE:
            raise NumberRangeError("the crystal count would exceed the exact integer range")
        after = state.copy()
        after.crystals[at] = here + 1
        if after.bag != "infinite":
            after.bag -= 1
        after.rev += 1
        tx.after = after
        tx.fx.update(cell_after=here + 1, bag_after=after.bag)
        return tx
    if op == "on_crystal":
        tx.result = here > 0
        tx.fx = {"subject": "crystal", "cell": list(at), "count": here}
        return tx
    if op == "crystal_count":
        tx.result = here
        tx.fx = {"subject": "count", "cell": list(at), "count": here}
        return tx
    if op == "bag_empty":
        tx.result = state.bag == 0
        tx.fx = {"subject": "bag", "bag": state.bag}
        return tx
    if op == "bag_count":
        tx.result = None if state.bag == "infinite" else state.bag
        tx.fx = {"subject": "bag", "bag": state.bag}
        return tx
    if op == "paint":
        fresh = at not in state.painted
        tx.fx = {"cell": list(at), "fresh": fresh}
        if fresh:
            after = state.copy()
            after.painted.add(at)
            after.rev += 1
            tx.after = after
        return tx
    if op == "erase":
        had = at in state.painted
        tx.fx = {"cell": list(at), "had": had}
        if had:
            after = state.copy()
            after.painted.discard(at)
            after.rev += 1
            tx.after = after
        return tx
    if op == "painted":
        tx.result = at in state.painted
        tx.fx = {"subject": "paint", "cell": list(at)}
        return tx
    raise CommandUnavailableError(f"{op}() is not implemented")  # pragma: no cover
