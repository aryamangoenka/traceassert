# the cli. this is still the vertical-slice version: findings come out as
# ugly prints, the real report card is step 8. exit 1 on FAIL findings so it
# already behaves like a test runner in CI.

from __future__ import annotations

import sys

from .judge import JevJudge
from .parser import find_traces, parse_trace
from .rules import run_rules


def main(argv: list[str] | None = None, judge=None) -> int:
    # judge is injectable so tests never touch the network, real runs use jev
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != "test":
        print("usage: traceassert test <trace.jsonl | folder of traces>")
        return 2

    paths = find_traces(argv[1])
    if not paths:
        print(f"no .jsonl traces found at {argv[1]}")
        return 2

    if judge is None:
        try:
            judge = JevJudge()
        except RuntimeError as e:
            print(e)
            return 2

    failed = 0
    for path in paths:
        trace = parse_trace(path)
        questions, _, findings = run_rules(trace, judge)
        print(f"{path}: {len(trace.events)} events, {len(questions)} judgments, {len(findings)} findings")
        for f in findings:
            print(f"  {f.status} [{f.rule_id}] {f.confidence:.2f}  {f.summary}  (events {f.event_ids})")
        failed += sum(1 for f in findings if f.status == "FAIL")

    s = judge.stats
    print(f"\n{s.questions} judgments in {s.calls} calls, {s.wall_seconds:.2f}s, "
          f"{s.input_tokens} tokens in, ${s.cost_usd:.6f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
