import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tlfrobot import maps
from tlfrobot.checking import (ACCEPTED, PRESENTATION_ERROR, WRONG_ANSWER, check_stream)
from tlfrobot.checking.ejudge import main as ejudge_main
from conftest import CORRIDOR, edit, run, trace_bytes, world

GOOD = """
from tlfrobot import *
move(); move()
while on_crystal():
    take()
while front_clear():
    move()
"""


def check(w, lines, goal="embedded"):
    return check_stream(w, trace_bytes(lines), w.goal if goal == "embedded" else goal)


@pytest.fixture
def good(corridor):
    res, lines = run(GOOD, corridor)
    assert res.status == "completed"
    return corridor, lines


def test_accepts_good(good):
    w, lines = good
    assert check(w, lines).verdict == ACCEPTED


def test_wrong_goal(corridor):
    res, lines = run("from tlfrobot import *\nmove()\n", corridor)
    r = check(corridor, lines)
    assert r.verdict == WRONG_ANSWER and r.code == "GOAL_NOT_MET"
    assert "(4, 0)" in r.message


def test_forged_sensor(good):
    w, lines = good
    idx = next(i for i, l in enumerate(lines) if '"op":"on_crystal"' in l)
    r = check(w, edit(lines, idx, result=False))
    assert r.code == "FORGED_RESULT"


def test_sensor_type_is_strict(good):
    w, lines = good
    idx = next(i for i, l in enumerate(lines) if '"op":"on_crystal"' in l)
    assert check(w, edit(lines, idx, result=1)).code == "FORGED_RESULT"


def test_forged_final_state(good):
    w, lines = good
    end = json.loads(lines[-1])
    end["state"]["robot"]["bag"] = 5
    lines = lines[:-1] + [json.dumps(end) + "\n"]
    assert check(w, lines).code == "FORGED_STATE"


def test_skipped_call_number(good):
    w, lines = good
    assert check(w, edit(lines, 2, n=7)).code == "BAD_SEQUENCE"


def test_duplicate_key(good):
    w, lines = good
    bad = list(lines)
    bad[1] = bad[1][:-2] + ',"op":"move"}\n'
    assert check(w, bad).verdict == PRESENTATION_ERROR


def test_nan_and_blank_and_truncated(good):
    w, lines = good
    bad = list(lines)
    bad[1] = bad[1].replace('"rev":1', '"rev":NaN')
    assert check(w, bad).verdict == PRESENTATION_ERROR
    assert check(w, lines[:2] + ["\n"] + lines[2:]).verdict == PRESENTATION_ERROR
    assert check(w, lines[:-1]).verdict == PRESENTATION_ERROR
    cut = lines[:-1] + [lines[-1][:-1]]
    assert check(w, cut).verdict == PRESENTATION_ERROR


def test_extra_after_end(good):
    w, lines = good
    extra = json.dumps({"t": "output", "s": len(lines), "stream": "stdout", "text": "x"}) + "\n"
    assert check(w, lines + [extra]).verdict == PRESENTATION_ERROR


def test_illegal_move_claimed_success(corridor):
    res, lines = run("from tlfrobot import *\nturn_left()\nmove()\n", corridor)
    assert res.error["code"] == "WALL_COLLISION"
    forged = edit(lines, 2, error=..., rev=2)
    r = check(corridor, forged)
    assert r.code == "ILLEGAL_ACTION"


def test_error_then_claimed_success(corridor):
    res, lines = run("from tlfrobot import *\nturn_left()\nmove()\n", corridor)
    end = json.loads(lines[-1])
    end["status"] = "completed"
    end.pop("error")
    assert check(corridor, lines[:-1] + [json.dumps(end) + "\n"]).code == "FORGED_STATUS"


def test_world_error_is_wrong_answer_with_reason(corridor):
    res, lines = run("from tlfrobot import *\nturn_left()\nmove()\n", corridor)
    r = check(corridor, lines)
    assert r.verdict == WRONG_ANSWER and r.code == "WALL_COLLISION"


def test_trace_from_another_world(good):
    w, lines = good
    other = maps.loads_world(CORRIDOR.replace("count = 2", "count = 3"))
    assert check(other, lines, goal=other.goal).code == "WORLD_MISMATCH"


def test_handwritten_trace_cannot_skip_rules(corridor):
    start = run("", corridor)[1][0]
    end = {"t": "end", "s": 1, "status": "completed", "rev": 0, "calls": 0,
           "state": {"robot": {"at": [4, 0], "heading": "east", "bag": 2}, "crystals": [], "painted": [],
                     "time_us": 0}}
    assert check(corridor, [start, json.dumps(end) + "\n"]).code == "FORGED_STATE"


def test_unknown_operation(good):
    w, lines = good
    assert check(w, edit(lines, 1, op="teleport")).code == "UNKNOWN_OPERATION"


ROOM = """
format = "tlfrobot-world/1"
id = "room"
[rules]
movement = "absolute"
[board]
size = [3, 2]
[robot]
at = [0, 0]
[goal.visits]
mode = "all_reachable"
"""


def test_empty_program_cannot_pass_all_reachable():
    w = world(ROOM)
    res, lines = run("", w)
    r = check(w, lines)
    assert r.verdict == WRONG_ANSWER and r.code == "GOAL_NOT_MET"


def test_all_reachable_full_walk():
    w = world(ROOM)
    res, lines = run("from tlfrobot import *\neast(); east(); north(); west(); west()\n", w)
    assert check(w, lines).verdict == ACCEPTED


def test_forbid_revisits():
    w = world(ROOM + "forbid_revisits = true\n")
    res, lines = run("from tlfrobot import *\neast(); east(); north(); west(); west(); south()\n", w)
    r = check(w, lines)
    assert r.code == "GOAL_NOT_MET" and "already visited" in r.message


def test_ejudge_exit_codes(tmp_path, good, corridor):
    w, lines = good
    m = tmp_path / "01.dat"
    m.write_text(CORRIDOR)
    out = tmp_path / "out"
    out.write_text("".join(lines))
    goal = tmp_path / "01.a"
    goal.write_text('format = "tlfrobot-goal/1"\n[goal]\nrobot_at = [4, 0]\n')
    assert ejudge_main(["check", str(m), str(out), str(goal)]) == 0
    goal.write_text('format = "tlfrobot-goal/1"\n[goal]\nrobot_at = [3, 0]\n')
    assert ejudge_main(["check", str(m), str(out), str(goal)]) == 1
    out.write_text("garbage\n")
    assert ejudge_main(["check", str(m), str(out), str(goal)]) == 2
    goal.write_text("not toml [")
    assert ejudge_main(["check", str(m), str(out), str(goal)]) == 6


def test_ejudge_auto_mode_end_to_end(tmp_path):
    src = tmp_path / "solution.py"
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "TLFROBOT_MODE": "ejudge", "PYTHONPATH": str(root / "src")}

    def go(code):
        src.write_text(code)
        return subprocess.run([sys.executable, str(src)], input=CORRIDOR.encode(), capture_output=True, env=env)

    p = go(GOOD + "print('hi')\n")
    assert p.returncode == 0
    w = maps.loads_world(CORRIDOR)
    assert check_stream(w, io.BytesIO(p.stdout), w.goal).verdict == ACCEPTED
    # a wall crash: exit 0 with a complete end record, so the checker explains it
    p = go("from tlfrobot import *\nturn_left()\nmove()\n")
    assert p.returncode == 0
    r = check_stream(w, io.BytesIO(p.stdout), w.goal)
    assert r.code == "WALL_COLLISION"
    # an ordinary Python crash stays a crash (traceback, non-zero exit)
    p = go("from tlfrobot import *\nmove()\n1/0\n")
    assert p.returncode == 1 and b"ZeroDivisionError" in p.stderr
    # a hand-written fake trace is not accepted
    p = go('print(\'{"t":"start"}\')\n')
    assert check_stream(w, io.BytesIO(p.stdout), w.goal).verdict != ACCEPTED


def test_cli_round_trip(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    ex = root / "examples" / "karel-b2"
    p = subprocess.run([sys.executable, "-m", "tlfrobot", "run", str(ex / "solution.py")],
                       capture_output=True, env=env, cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    trace = tmp_path / "t.jsonl"
    trace.write_bytes(p.stdout)
    q = subprocess.run([sys.executable, "-m", "tlfrobot", "check", str(ex / "map.toml"), str(trace)],
                       capture_output=True, env=env)
    assert q.returncode == 0, q.stdout
