# the cli. exit 1 on FAIL findings so it behaves like a test runner in CI.

from __future__ import annotations

import argparse
import sys

from .check import CONTRADICTED, build_receipts
from .judge import JevJudge
from .parser import find_traces, parse_trace
from .report import render, render_receipts, render_stats
from .rules import all_rules, run_rules


def main(argv: list[str] | None = None, judge=None) -> int:
    # judge is injectable so tests never touch the network, real runs use jev
    parser = argparse.ArgumentParser(
        prog="traceassert",
        description="check what your agent actually did against what it said",
    )
    sub = parser.add_subparsers(dest="cmd")

    # the pivot's command: claim -> evidence -> verdict, deterministic, no jev
    check = sub.add_parser("check", help="attest the agent's claims against the trace")
    check.add_argument("path", help="a .jsonl trace or a folder of them")

    # the old rule engine, kept working while the pivot proves out
    test = sub.add_parser("test", help="run the semantic rules against traces")
    test.add_argument("path", help="a .jsonl trace or a folder of them")
    test.add_argument(
        "--prohibit", action="append", default=[], metavar="GLOB",
        help="path pattern the agent was told not to touch (repeatable), e.g. 'src/auth/*'",
    )

    try:
        args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as e:  # argparse exits on bad args, we return instead
        return int(e.code or 2)
    if args.cmd not in ("check", "test"):
        parser.print_help()
        return 2

    paths = find_traces(args.path)
    if not paths:
        print(f"no .jsonl traces found at {args.path}")
        return 2

    if args.cmd == "check":
        return _cmd_check(paths, judge)
    return _cmd_test(paths, args.prohibit, judge)


def _cmd_check(paths, judge) -> int:
    # the deterministic core needs no key. jev is optional here, it only routes
    # claims to evidence, and without a key those receipts say so honestly.
    # exit 1 if any claim is CONTRADICTED, that's the ci-gate value.
    if judge is None:
        try:
            judge = JevJudge()
        except RuntimeError:
            judge = None
    contradicted = 0
    for i, path in enumerate(paths):
        if i:
            print("\n")
        trace = parse_trace(path)
        receipts = build_receipts(trace, judge)
        print(render_receipts(trace, receipts))
        contradicted += sum(1 for r in receipts if r.verdict == CONTRADICTED)
    if judge is not None and judge.stats.calls:
        print()
        print(render_stats(judge.stats))
    return 1 if contradicted else 0


def _cmd_test(paths, prohibit, judge) -> int:
    if judge is None:
        try:
            judge = JevJudge()
        except RuntimeError as e:
            print(e)
            return 2

    rules = all_rules(prohibited=prohibit)
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
