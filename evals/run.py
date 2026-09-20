# smoke eval: is the judge roughly trustworthy on our seven question shapes?
# this is NOT calibration (that's ~500 labeled pairs per rule, later), it's
# the thing you run before polishing a report card around unreliable checks.
# questions and evidence are built the exact same way the rules build them,
# the templates are imported straight from rules.py so drift is impossible.
#
#   uv run python evals/run.py
#
# results land in evals/results/ as json, receipts culture applies to us too.

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from traceassert.judge import JevJudge, Question
from traceassert.rules import Q_AUTH, Q_DESTR, Q_NEWINFO, Q_SAME, Q_SCOPE, Q_SUMMARY, q_claim

HERE = Path(__file__).parent


def build_question(qid: str, kind: str, case: dict) -> Question:
    # evidence strings mirror the rules' formats exactly
    if kind == "claim_support":
        return Question(qid, q_claim(case["claim"]), case["evidence"])
    if kind == "scope_outside":
        ev = (f"user request: {case['request']}\n"
              f"file modified: {case['path']}\n"
              f"edit detail: {case.get('detail', '')}")
        return Question(qid, Q_SCOPE, ev)
    if kind == "destructive":
        return Question(qid, Q_DESTR, f"command: {case['command']}")
    if kind == "authorized":
        ev = f"user messages:\n{case['user_messages']}\n\ncommand that ran: {case['command']}"
        return Question(qid, Q_AUTH, ev)
    if kind == "same_action":
        ev = f"first attempt (failed):\n{case['first']}\n\nsecond attempt:\n{case['second']}"
        return Question(qid, Q_SAME, ev)
    if kind == "new_info":
        ev = f"the failure said:\n{case['failure']}\n\ngathered between the attempts:\n{case['between']}"
        return Question(qid, Q_NEWINFO, ev)
    if kind == "summary_accurate":
        ev = f"final summary:\n{case['summary']}\n\nfiles actually modified: {case['files']}"
        return Question(qid, Q_SUMMARY, ev)
    raise ValueError(f"unknown question kind: {kind}")


def main() -> int:
    data = json.loads((HERE / "cases.json").read_text())
    kinds = [k for k in data if not k.startswith("_")]

    questions, expected = [], {}
    for kind in kinds:
        for i, case in enumerate(data[kind]):
            qid = f"{kind}:{i}"
            questions.append(build_question(qid, kind, case))
            expected[qid] = case["expected"]

    judge = JevJudge()
    verdicts = judge.ask(questions)

    per_kind = defaultdict(lambda: {"n": 0, "correct": 0, "wrong": []})
    for qid, want in expected.items():
        kind, idx = qid.rsplit(":", 1)
        v = verdicts[qid]
        per_kind[kind]["n"] += 1
        if v.yes == want:
            per_kind[kind]["correct"] += 1
        else:
            case = data[kind][int(idx)]
            per_kind[kind]["wrong"].append({
                "case": case, "expected": want, "got": v.yes, "p_yes": round(v.p_yes, 3),
            })

    total_n = sum(k["n"] for k in per_kind.values())
    total_ok = sum(k["correct"] for k in per_kind.values())
    print(f"\nsmoke eval, {total_n} hand-labeled cases, {total_ok} correct "
          f"({100 * total_ok / total_n:.1f}%)\n")
    for kind in kinds:
        r = per_kind[kind]
        flag = "" if r["correct"] == r["n"] else "  <-- look here"
        print(f"  {kind:<18} {r['correct']:>2}/{r['n']}{flag}")
        for w in r["wrong"]:
            note = w["case"].get("note", "")
            print(f"      missed: expected {w['expected']}, got {w['got']} (p_yes {w['p_yes']}) {('[' + note + ']') if note else ''}")

    s = judge.stats
    print(f"\nmeasured: {s.questions} judgments, {s.calls} calls, {s.wall_seconds:.2f}s wall, "
          f"{s.input_tokens} tokens in, ${s.cost_usd:.6f}")

    out = {
        "date": str(date.today()),
        "total": {"n": total_n, "correct": total_ok},
        "per_kind": {k: {"n": v["n"], "correct": v["correct"], "wrong": v["wrong"]} for k, v in per_kind.items()},
        "stats": {"judgments": s.questions, "calls": s.calls, "wall_seconds": round(s.wall_seconds, 3),
                  "input_tokens": s.input_tokens, "output_tokens": s.output_tokens,
                  "cost_usd": round(s.cost_usd, 8)},
    }
    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"{date.today()}-smoke.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
