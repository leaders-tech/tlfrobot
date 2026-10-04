import subprocess
import sys
from pathlib import Path

from tlfrobot import maps
from tlfrobot.authoring import Board


def test_board_round_trip():
    b = Board(5, 3, robot=(0, 0), heading="east", bag=0)
    b.wall_h(1, 1, 3).wall_east(4, 0).crystal(2, 0, 3).finish(4, 2).target(1, 1)
    w = maps.loads_world(b.toml(id="x"))
    assert w.blocked((1, 0), "north") and w.blocked((2, 0), "north") and not w.blocked((3, 0), "north")
    assert w.crystals == {(2, 0): 3}
    assert {m["kind"] for m in w.presentation["markers"]} == {"finish", "target"}


def test_goal_cli(tmp_path):
    root = Path(__file__).resolve().parents[1]
    ex = root / "examples" / "karel-b2"
    p = subprocess.run([sys.executable, "-m", "tlfrobot", "goal", str(ex / "solution.py"), "--parts", "robot_at,bag,crystals"],
                       input=(ex / "map.toml").read_bytes(), capture_output=True, env={"PYTHONPATH": str(root / "src")})
    assert p.returncode == 0, p.stderr
    w = maps.load_world(ex / "map.toml")
    g = maps.loads_goal(p.stdout, w)
    assert g.robot_at == (4, 0) and g.bag == 1 and g.crystals == {}
