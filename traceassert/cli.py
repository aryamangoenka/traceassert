# the cli. exit 1 on FAIL findings so it behaves like a test runner in CI.

from __future__ import annotations

import argparse
import sys

from .judge import JevJudge
from .parser import find_traces, parse_trace
from .report import render, render_stats
from .rules import all_rules, run_rules


def main(argv: list[str] | None = None, judge=None) -> int:
    # judge is injectable so tests never touch the network, real runs use jev
    parser = argparse.ArgumentParser(
        prog="traceassert",
        description="tests what your agent actually did",
    )
    sub = parser.add_subparsers(dest="cmd")
    test = sub.add_parser("test", help="run the rules against traces")
    test.add_argument("path", help="a .jsonl trace or a folder of them")
    test.add_argument(
        "--prohibit", action="append", default=[], metavar="GLOB",
        help="path pattern the agent was told not to touch (repeatable), e.g. 'src/auth/*'",
    )

    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as e:  # argparse exits on bad args, we return instead
        return int(e.code or 2)
    if args.cmd != "test":
        parser.print_help()
        return 2

    paths = find_traces(args.path)
    if not paths:
        print(f"no .jsonl traces found at {args.path}")
        return 2

    if judge is None:
        try:
            judge = JevJudge()
        except RuntimeError as e:
            print(e)
            return 2

    rules = all_rules(prohibited=args.prohibit)
    failed = 0
    for i, path in enumerate(paths):
        if i:
            print("\n")
        trace = parse_trace(path)
        questions, _, findings = run_rules(trace, judge, rules)
        print(render(trace, questions, findings))
        failed += sum(1 for f in findings if f.status == "FAIL")

    print()
    print(render_stats(judge.stats))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
