"""ejudge checker adapter.

    check_cmd = "check"    # a script: from tlfrobot.checking.ejudge import main; raise SystemExit(main())

ejudge calls `check <input> <output> [<answer>]`: the input is the trusted
world, the output is the contestant's trace, the answer (with use_corr) the
private goal. Exit codes: 0 OK, 1 WA, 2 PE; anything else (we use 6) is a check failure.
The message goes to stdout, which ejudge shows as the checker's comment.
"""
from __future__ import annotations

import sys
import traceback

from . import (ACCEPTED, CHECKER_ERROR, PRESENTATION_ERROR, WRONG_ANSWER, CheckResult, check_stream)
from .. import maps
from ..errors import MapError

EXIT = {ACCEPTED: 0, WRONG_ANSWER: 1, PRESENTATION_ERROR: 2, CHECKER_ERROR: 6}


def run(argv: list[str]) -> CheckResult:
    if len(argv) < 3:
        return CheckResult(CHECKER_ERROR, "USAGE", "usage: check INPUT OUTPUT [ANSWER]")
    try:
        world = maps.load_world(argv[1])
        goal = maps.load_goal(argv[3], world) if len(argv) > 3 else world.goal
    except (MapError, OSError) as e:
        return CheckResult(CHECKER_ERROR, "BAD_TASK", f"invalid task files: {e}")
    if goal is None:
        return CheckResult(CHECKER_ERROR, "NO_GOAL", "no goal: give an answer file or embed [goal] in the world")
    with open(argv[2], "rb") as fh:
        return check_stream(world, fh, goal)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    try:
        res = run(argv)
    except Exception:  # noqa: BLE001 - a checker crash must be a check failure, never OK
        traceback.print_exc()
        res = CheckResult(CHECKER_ERROR, "CHECKER_CRASH", "the checker crashed")
    print(f"{res.code}: {res.message}")
    sys.stdout.flush()
    if not res.accepted:
        # ejudge shows the checker's stderr in the report; say it there too.
        print(f"{res.code}: {res.message}", file=sys.stderr)
    return EXIT[res.verdict]
