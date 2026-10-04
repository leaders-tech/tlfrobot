"""python -m tlfrobot run | validate | check | catalog"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m tlfrobot")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a program against a world")
    r.add_argument("source")
    r.add_argument("--map", dest="map_source", help="world file, or - for stdin (default: map.toml next to SOURCE)")
    r.add_argument("--world", dest="world_alias", help=argparse.SUPPRESS)
    r.add_argument("--mode", default="headless", choices=["headless", "ejudge", "desktop"])
    r.add_argument("--trace", help="also write the trace to this file")
    v = sub.add_parser("validate", help="check a world file")
    v.add_argument("map")
    c = sub.add_parser("check", help="replay a trace and check the goal")
    c.add_argument("map")
    c.add_argument("trace", help="trace file, or - for stdin")
    c.add_argument("--goal")
    g = sub.add_parser("goal", help="run a reference solution on a world (stdin) and print the goal it reaches")
    g.add_argument("solution")
    g.add_argument("--parts", default="robot_at,crystals",
                   help="comma-separated: robot_at, robot_heading, bag, crystals, paint")
    g.add_argument("--map", dest="map_source", default="-")
    sub.add_parser("catalog", help="print the function catalogue as JSON")
    args = p.parse_args(argv)

    if args.cmd == "run":
        from .runtime import run_file
        if args.world_alias and args.map_source:
            p.error("use --map only (--world is its old name)")
        if args.mode == "desktop":
            print("tlfrobot: the desktop window is not available in this release; use --mode headless",
                  file=sys.stderr)
            return 2
        if args.trace and args.mode != "desktop":
            p.error("in headless mode stdout already is the trace; redirect it instead of --trace")
        return run_file(args.source, map_source=args.map_source or args.world_alias, mode=args.mode)
    if args.cmd == "validate":
        from .errors import MapError
        from .maps import load_world
        try:
            world = load_world(args.map)
        except (MapError, OSError) as e:
            print(e, file=sys.stderr)
            return 2
        print(json.dumps(world.normalised(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "check":
        from . import maps
        from .checking import CHECKER_ERROR, check_stream, CheckResult
        from .errors import MapError
        try:
            world = maps.load_world(args.map)
            goal = maps.load_goal(args.goal, world) if args.goal else world.goal
        except (MapError, OSError) as e:
            res = CheckResult(CHECKER_ERROR, "BAD_TASK", str(e))
        else:
            if args.trace == "-":
                res = check_stream(world, sys.stdin.buffer, goal)
            else:
                with open(args.trace, "rb") as fh:
                    res = check_stream(world, fh, goal)
        print(json.dumps(res.as_json(), ensure_ascii=False, indent=2))
        return 0 if res.accepted else 1
    if args.cmd == "goal":
        from . import maps
        from .authoring import goal_from_state
        from .runtime import resolve_map, run_source
        from pathlib import Path
        src = Path(args.solution)
        world = resolve_map(src, args.map_source)
        res = run_source(src.read_text(encoding="utf-8"), world, filename=src.name, capture_output=True)
        if res.status != "completed":
            print(f"tlfrobot goal: the reference solution did not complete: {res.status} {res.error}", file=sys.stderr)
            return 1
        sys.stdout.write(goal_from_state(world, res.state, [p for p in args.parts.split(",") if p]))
        return 0
    if args.cmd == "catalog":
        from .catalog import as_json
        print(json.dumps(as_json(), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
