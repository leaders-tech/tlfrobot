"""Write src/tlfrobot/__init__.py from the catalogue (`--check` only compares)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tlfrobot.catalog import FUNCTIONS  # noqa: E402

HEAD = '''"""tlfrobot — a grid robot for learning Python.

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

'''

TAIL = '''

if _os.environ.get("TLFROBOT_MODE") == "ejudge" and _runtime._current is None:
    _runtime.start_ejudge_auto()
'''


def render() -> str:
    out = [HEAD, "__all__ = [\n"]
    out += [f'    "{f.name}",\n' for f in FUNCTIONS]
    out.append("]\n")
    for f in FUNCTIONS:
        out.append(f'\n\ndef {f.name}() -> {f.returns}:\n    """{f.en}\n\n'
                   f'    Needs: {", ".join(f.requires)}."""\n    return _runtime.call("{f.name}")\n')
    out.append(TAIL)
    return "".join(out)


if __name__ == "__main__":
    target = ROOT / "src" / "tlfrobot" / "__init__.py"
    text = render()
    if "--check" in sys.argv:
        sys.exit(0 if target.read_text() == text else 1)
    target.write_text(text)
