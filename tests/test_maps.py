import pytest

from tlfrobot.errors import MapError
from conftest import world

HEAD = 'format = "tlfrobot-world/1"\nid = "t"\n[rules]\nmovement = "relative"\n'


def test_ascii_equals_structured():
    a = world(HEAD + """
[board]
ascii = '''
+---+---+---+---+
| .   .   .   . |
+   +---+   +   +
| .   . | .   . |
+   +   +   +   +
| .   .   .   . |
+---+---+---+---+
'''
[robot]
at = [0, 0]
heading = "east"
""")
    b = world(HEAD + """
[board]
size = [4, 3]
walls = [{ axis = "h", at = 2, span = [1, 2] }, { axis = "v", at = 2, span = [1, 2] },
         { axis = "h", at = 0, span = [0, 4] }]
[robot]
at = [0, 0]
heading = "east"
""")
    assert a.normalised()["board"] == b.normalised()["board"]
    assert a.blocked((1, 1), "north")
    assert a.blocked((1, 1), "east")
    assert not a.blocked((1, 1), "south")
    assert a.blocked((0, 0), "west") and a.blocked((0, 0), "south")


def test_ascii_contour_must_be_closed():
    with pytest.raises(MapError, match="closed"):
        world(HEAD + """
[board]
ascii = '''
+---+   +
| .   . |
+---+---+
'''
[robot]
at = [0, 0]
heading = "east"
""")


def test_ascii_bad_cell():
    with pytest.raises(MapError, match="line 2"):
        world(HEAD + """
[board]
ascii = '''
+---+
| x |
+---+
'''
[robot]
at = [0, 0]
heading = "east"
""")


def test_one_by_one_board():
    w = world(HEAD + '[board]\nsize = [1, 1]\n[robot]\nat = [0, 0]\nheading = "north"\n')
    assert all(w.blocked((0, 0), d) for d in ("north", "south", "east", "west"))


def test_unknown_key_is_an_error():
    with pytest.raises(MapError, match="unknown key 'colour'"):
        world(HEAD + '[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\nheading = "north"\ncolour = 1\n')


def test_heading_rules():
    with pytest.raises(MapError, match="needs 'heading'"):
        world(HEAD + '[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\n')
    with pytest.raises(MapError, match="no heading"):
        world(HEAD.replace("relative", "absolute") + '[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\nheading = "north"\n')


def test_bag_requires_crystals():
    with pytest.raises(MapError, match="crystals"):
        world(HEAD + '[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\nheading = "north"\nbag = 1\n')
    with pytest.raises(MapError, match="bag"):
        world(HEAD + 'tools = ["crystals"]\n[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\nheading = "north"\n')


def test_layer_of_disabled_tool_rejected():
    with pytest.raises(MapError, match="paint"):
        world(HEAD + '[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\nheading = "north"\n[cells]\npainted = [[0, 0]]\n')


def test_duplicate_cells_rejected():
    with pytest.raises(MapError, match="duplicate"):
        world(HEAD + 'tools = ["crystals"]\n[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\nheading = "north"\nbag = 0\n'
              '[cells]\ncrystals = [{ at = [1, 1], count = 1 }, { at = [1, 1], count = 2 }]\n')


def test_boolean_is_not_an_integer():
    with pytest.raises(MapError, match="integer"):
        world(HEAD + '[board]\nsize = [true, 2]\n[robot]\nat = [0, 0]\nheading = "north"\n')


def test_wall_outside_board():
    with pytest.raises(MapError, match="outside"):
        world(HEAD + '[board]\nsize = [2, 2]\nwalls = [{ axis = "h", at = 1, span = [0, 3] }]\n'
              '[robot]\nat = [0, 0]\nheading = "north"\n')


def test_overlapping_walls_merge_and_outer_walls_vanish():
    w = world(HEAD + '[board]\nsize = [6, 3]\nwalls = [{ axis = "h", at = 1, span = [0, 3] }, '
              '{ axis = "h", at = 1, span = [2, 5] }, { axis = "h", at = 1, span = [5, 6] }, '
              '{ axis = "v", at = 6, span = [0, 3] }]\n[robot]\nat = [0, 0]\nheading = "north"\n')
    assert w.normalised()["board"]["walls"] == [{"axis": "h", "at": 1, "span": [0, 6]}]


def test_plane_rays_and_gaps():
    w = world(HEAD + """
[board]
topology = "plane"
walls = [{ axis = "h", at = 1, span = ["-inf", "+inf"], gaps = [[7, 8]] }]
[robot]
at = [0, 0]
heading = "north"
""")
    assert w.blocked((-1000, 0), "north")
    assert w.blocked((10**9, 0), "north")
    assert not w.blocked((7, 0), "north")
    assert not w.blocked((-5, -5), "west")
    assert w.normalised()["board"]["walls"] == [
        {"axis": "h", "at": 1, "span": ["-inf", 7]}, {"axis": "h", "at": 1, "span": [8, "+inf"]}]
    assert "viewport" in w.presentation


def test_infinite_ends_only_on_plane():
    with pytest.raises(MapError, match="plane"):
        world(HEAD + '[board]\nsize = [2, 2]\nwalls = [{ axis = "h", at = 1, span = ["-inf", 1] }]\n'
              '[robot]\nat = [0, 0]\nheading = "north"\n')


def test_counts_needs_crystals_and_compass_needs_relative():
    with pytest.raises(MapError, match="counts"):
        world(HEAD + 'sensors = ["counts"]\n[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\nheading = "north"\n')
    with pytest.raises(MapError, match="compass"):
        world(HEAD.replace("relative", "absolute") + 'sensors = ["compass"]\n[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\n')


def test_allowed_commands_restricts():
    w = world(HEAD + 'allowed_commands = ["move", "turn_left", "paint"]\n[board]\nsize = [2, 2]\n'
              '[robot]\nat = [0, 0]\nheading = "north"\n')
    assert w.allowed == {"move", "turn_left"}


def test_inputs_not_in_this_release():
    with pytest.raises(MapError, match="not available"):
        world(HEAD + 'inputs = ["keyboard"]\n[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\nheading = "north"\n')


def test_bad_utf8_and_size():
    from tlfrobot import maps
    with pytest.raises(MapError, match="UTF-8"):
        maps.loads_world(b"\xff\xfe")
    with pytest.raises(MapError, match="larger"):
        maps.loads_world(b"#" * 100, max_bytes=10)


def test_goal_validation():
    with pytest.raises(MapError, match="robot_heading"):
        world(HEAD.replace("relative", "absolute") + '[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\n'
              '[goal]\nrobot_heading = "north"\n')
