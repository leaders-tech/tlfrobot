"""The public robot functions: one list that the Python exports, the browser's
completion and the documentation are all generated from.

`requires` names capabilities a world must enable (all of them) for the
function to be callable. A movement policy is a capability too: `relative` or
`absolute`.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Function:
    name: str
    kind: str  # "action" | "sensor"
    returns: str  # Python annotation as shown to a student
    requires: tuple[str, ...]
    clip: str
    en: str
    ru: str
    signature: str = ""

    def __post_init__(self) -> None:
        if not self.signature:
            object.__setattr__(self, "signature", f"{self.name}()")


def _f(name, kind, returns, requires, clip, en, ru):
    return Function(name, kind, returns, tuple(requires), clip, en, ru)


FUNCTIONS: tuple[Function, ...] = (
    _f("move", "action", "None", ["relative"], "C01",
       "Move forward by one cell.", "Сделать шаг вперёд на одну клетку."),
    _f("turn_left", "action", "None", ["relative"], "C02",
       "Turn 90° to the left on the spot.", "Повернуться налево на месте."),
    _f("turn_right", "action", "None", ["relative"], "C02",
       "Turn 90° to the right on the spot.", "Повернуться направо на месте."),
    _f("turn_around", "action", "None", ["relative"], "C02",
       "Turn around (180°) on the spot.", "Развернуться на месте."),
    _f("front_clear", "sensor", "bool", ["relative"], "C06",
       "True if there is no wall in front.", "Впереди нет стены?"),
    _f("left_clear", "sensor", "bool", ["relative"], "C06",
       "True if there is no wall on the left.", "Слева нет стены?"),
    _f("right_clear", "sensor", "bool", ["relative"], "C06",
       "True if there is no wall on the right.", "Справа нет стены?"),
    _f("back_clear", "sensor", "bool", ["relative"], "C06",
       "True if there is no wall behind.", "Сзади нет стены?"),
    _f("north", "action", "None", ["absolute"], "C01",
       "Step one cell north (up).", "Шаг на север (вверх)."),
    _f("south", "action", "None", ["absolute"], "C01",
       "Step one cell south (down).", "Шаг на юг (вниз)."),
    _f("east", "action", "None", ["absolute"], "C01",
       "Step one cell east (right).", "Шаг на восток (вправо)."),
    _f("west", "action", "None", ["absolute"], "C01",
       "Step one cell west (left).", "Шаг на запад (влево)."),
    _f("north_clear", "sensor", "bool", ["absolute"], "C06",
       "True if there is no wall to the north.", "На севере свободно?"),
    _f("south_clear", "sensor", "bool", ["absolute"], "C06",
       "True if there is no wall to the south.", "На юге свободно?"),
    _f("east_clear", "sensor", "bool", ["absolute"], "C06",
       "True if there is no wall to the east.", "На востоке свободно?"),
    _f("west_clear", "sensor", "bool", ["absolute"], "C06",
       "True if there is no wall to the west.", "На западе свободно?"),
    _f("take", "action", "None", ["crystals"], "C03",
       "Pick up one crystal from this cell into the bag.", "Взять один кристалл с клетки в сумку."),
    _f("put", "action", "None", ["crystals"], "C03",
       "Put one crystal from the bag onto this cell.", "Положить один кристалл из сумки на клетку."),
    _f("on_crystal", "sensor", "bool", ["crystals"], "C07",
       "True if this cell has at least one crystal.", "На клетке есть кристалл?"),
    _f("bag_empty", "sensor", "bool", ["crystals"], "C08",
       "True if the bag has no crystals (never for an infinite bag).", "Сумка пуста?"),
    _f("paint", "action", "None", ["paint"], "C04",
       "Paint this cell.", "Закрасить клетку."),
    _f("painted", "sensor", "bool", ["paint"], "C07",
       "True if this cell is painted.", "Клетка закрашена?"),
    _f("erase", "action", "None", ["paint", "eraser"], "C05",
       "Remove the paint from this cell.", "Стереть краску с клетки."),
    _f("facing_north", "sensor", "bool", ["relative", "compass"], "C09",
       "True if the robot faces north.", "Робот смотрит на север?"),
    _f("facing_south", "sensor", "bool", ["relative", "compass"], "C09",
       "True if the robot faces south.", "Робот смотрит на юг?"),
    _f("facing_east", "sensor", "bool", ["relative", "compass"], "C09",
       "True if the robot faces east.", "Робот смотрит на восток?"),
    _f("facing_west", "sensor", "bool", ["relative", "compass"], "C09",
       "True if the robot faces west.", "Робот смотрит на запад?"),
    _f("crystal_count", "sensor", "int", ["crystals", "counts"], "C07",
       "How many crystals lie on this cell.", "Сколько кристаллов на клетке."),
    _f("bag_count", "sensor", "int | None", ["crystals", "counts"], "C08",
       "How many crystals are in the bag (None if it is infinite).",
       "Сколько кристаллов в сумке (None, если сумка бесконечная)."),
)

BY_NAME: dict[str, Function] = {f.name: f for f in FUNCTIONS}
NAMES: tuple[str, ...] = tuple(f.name for f in FUNCTIONS)

MOVEMENTS = ("relative", "absolute")
TOOLS = ("crystals", "paint", "eraser")
SENSORS = ("compass", "counts")
INPUTS = ("keyboard", "pointer")


def as_json() -> dict:
    from ._version import __version__

    return {
        "format": "tlfrobot-catalog/1",
        "version": __version__,
        "functions": [asdict(f) for f in FUNCTIONS],
    }
