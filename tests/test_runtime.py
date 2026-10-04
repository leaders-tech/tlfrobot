import pytest

import tlfrobot
from tlfrobot import catalog, core
from tlfrobot.errors import WorldNotLoadedError
from conftest import CORRIDOR, run, world

ABS = """
format = "tlfrobot-world/1"
id = "abs"
[rules]
movement = "absolute"
tools = ["paint", "eraser", "crystals"]
[board]
size = [3, 3]
walls = [{ axis = "v", at = 1, span = [0, 1] }]
[robot]
at = [0, 0]
bag = "infinite"
"""


def test_exports_match_catalogue():
    assert tlfrobot.__all__ == list(catalog.NAMES)
    assert len(catalog.NAMES) == 29
    assert set(dir(tlfrobot)) >= set(catalog.NAMES)


def test_init_is_generated():
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert subprocess.run([sys.executable, str(root / "tools" / "gen_init.py"), "--check"]).returncode == 0


def test_outside_session():
    with pytest.raises(WorldNotLoadedError, match="python -m tlfrobot run"):
        tlfrobot.move()


@pytest.mark.parametrize("start,op,end", [
    ("north", "turn_left", "west"), ("west", "turn_left", "south"), ("south", "turn_left", "east"),
    ("east", "turn_left", "north"), ("north", "turn_right", "east"), ("west", "turn_right", "north"),
    ("north", "turn_around", "south"), ("east", "turn_around", "west"),
])
def test_turns(start, op, end):
    assert core.turn(start, core.TURN[op]) == end


def test_relative_sensors_follow_heading():
    w = world(CORRIDOR)  # 5x1 corridor, facing east at the west end
    res, _ = run("""
    from tlfrobot import *
    r = [front_clear(), left_clear(), right_clear(), back_clear()]
    turn_around()
    r += [front_clear(), back_clear()]
    print(r)
    """, w)
    assert res.status == "completed"
    out = [rec["text"] for rec in res.records if rec["t"] == "output"]
    assert out == ["[True, False, False, False, False, True]\n"]


def test_failure_is_terminal_even_if_caught(corridor):
    res, lines = run("""
    from tlfrobot import *
    from tlfrobot.errors import RobotError
    turn_left()
    try:
        move()
    except RobotError as e:
        print(e.code)
    try:
        turn_right()
    except RobotError as e:
        print(e.code)
    """, corridor)
    assert res.status == "error"
    assert res.error["code"] == "WALL_COLLISION"
    outs = [r["text"] for r in res.records if r["t"] == "output"]
    assert outs == ["WALL_COLLISION\n", "SESSION_FAILED\n"]
    assert res.state.heading == "north" and res.state.at == (0, 0)
    assert res.records[-1]["error"]["code"] == "WALL_COLLISION"


def test_short_circuit_skips_sensor(corridor):
    res, _ = run("""
    from tlfrobot import *
    if False and front_clear():
        pass
    if True or on_crystal():
        pass
    """, corridor)
    assert res.calls == 0


def test_recursion_and_functions(corridor):
    res, _ = run("""
    from tlfrobot import *

    def to_wall():
        if front_clear():
            move()
            to_wall()

    def grab_all():
        while on_crystal():
            take()

    move(); move()
    grab_all()
    to_wall()
    print(bag_count(), crystal_count())
    """, corridor)
    assert res.status == "completed"
    assert res.state.at == (4, 0) and res.state.bag == 2


def test_take_put_finite_and_errors(corridor):
    res, _ = run("""
    from tlfrobot import *
    put()
    """, corridor)
    assert res.error["code"] == "EMPTY_BAG"
    res, _ = run("""
    from tlfrobot import *
    take()
    """, corridor)
    assert res.error["code"] == "NO_CRYSTAL"


def test_absolute_paint_erase_infinite_bag():
    w = world(ABS)
    res, _ = run("""
    from tlfrobot import *
    assert bag_empty() is False
    put(); put(); take()
    paint(); paint()
    assert painted()
    erase(); erase()
    assert not painted()
    north(); east()
    assert not west_clear() is False
    east()
    """, w)
    assert res.status == "completed", res.error
    assert res.state.bag == "infinite"
    assert res.state.crystals == {(0, 0): 1}
    assert res.state.at == (2, 1) and res.state.heading is None
    assert res.state.rev == 2 + 1 + 1 + 1 + 3  # put, put, take, paint, erase, 3 moves


def test_wall_in_absolute_mode():
    res, _ = run("from tlfrobot import *\neast()\n", world(ABS))
    assert res.error["code"] == "WALL_COLLISION"
    assert res.records[1]["line"] == 2


def test_unavailable_command(corridor):
    res, _ = run("from tlfrobot import *\npaint()\n", corridor)
    assert res.error["code"] == "COMMAND_UNAVAILABLE"
    assert "paint" in res.error["message"]


def test_arity_error_is_plain_typeerror(corridor):
    res, _ = run("from tlfrobot import *\nmove(4)\n", corridor)
    assert res.status == "error" and res.calls == 0
    assert res.error["details"]["type"] == "TypeError"


def test_syntax_error_keeps_student_line(corridor):
    res, lines = run("from tlfrobot import *\nmove()\nif True\n", corridor)
    assert res.error["code"] == "PYTHON_EXCEPTION"
    assert res.error["details"]["line"] == 3
    assert len(lines) == 2  # start + end


def test_python_exception_line(corridor):
    res, _ = run("from tlfrobot import *\nmove()\nx = 1 / 0\n", corridor)
    assert res.status == "error"
    assert res.error["details"]["line"] == 3
    assert "ZeroDivisionError" in res.error["message"]


def test_system_exit(corridor):
    res, _ = run("from tlfrobot import *\nmove()\nraise SystemExit(0)\nmove()\n", corridor)
    assert res.status == "completed" and res.calls == 1
    res, _ = run("import sys\nsys.exit(3)\n", corridor)
    assert res.status == "error"


def test_call_limit(corridor):
    res, _ = run("from tlfrobot import *\nwhile True:\n    front_clear()\n", corridor)
    assert res.status == "limit"
    assert res.calls == 100_000


def test_map_limits_tighten(corridor):
    from tlfrobot import maps
    w = maps.loads_world(CORRIDOR + "[limits]\nmax_calls = 3\n")
    res, _ = run("from tlfrobot import *\nfor _ in range(5):\n    front_clear()\n", w)
    assert res.status == "limit" and res.calls == 3


def test_cancel_transport(corridor):
    from tlfrobot.runtime import CallbackTransport, run_source
    calls = []

    def perform(req):
        calls.append(req["op"])
        return "cancelled" if len(calls) == 2 else "completed"

    res = run_source("from tlfrobot import *\nmove()\ntry:\n    move()\nexcept Exception:\n    pass\nmove()\n",
                     corridor, transport=CallbackTransport(perform), keep_records=True)
    assert res.status == "cancelled"
    assert res.state.at == (1, 0)  # the cancelled move was not committed
    assert calls == ["move", "move"]


def test_transport_sees_preview_before_commit(corridor):
    from tlfrobot.runtime import CallbackTransport, run_source, current
    seen = []

    def perform(req):
        seen.append((req["op"], req["fx"], current().state.at))
        return "completed"

    run_source("from tlfrobot import *\nmove()\nfront_clear()\n", corridor, transport=CallbackTransport(perform))
    assert seen[0] == ("move", {"from": [0, 0], "dir": "east", "to": [1, 0]}, (0, 0))
    assert seen[1][0] == "front_clear"


def test_visits_and_revisits(corridor):
    res, _ = run("from tlfrobot import *\nmove()\nturn_around()\nmove()\n", corridor)
    assert res.visits == [(0, 0), (1, 0), (0, 0)]
    assert res.revisited
