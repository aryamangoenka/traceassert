# smoke eval for the two pieces that had no number yet: the jev router (does it
# say the right things RELATE) and the regex classifier (does it put claims
# in the right bin). the deterministic verdicts already have a number behind
# them (grep), this gives the routed ones one too. not calibration, a smoke
# test, same methodology as evals/run.py.
#
#   uv run python evals/run_router.py
#
# questions and state are built with the exact helpers production uses,
# imported from check.py, so drift is impossible. results land in evals/results/.

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from traceassert.check import (
    MATCH_AT,
    NEG_CONTRADICT_AT,
    Q_ROUTE_CMD,
    Q_ROUTE_EDIT,
    Q_ROUTE_NEG,
    classify,
    route_state,
    route_text,
)
from traceassert.judge import JevJudge, Question

HERE = Path(__file__).parent
QUESTIONS = {
    "edit_relevance": Q_ROUTE_EDIT,
    "command_relevance": Q_ROUTE_CMD,
    "negative_touch": Q_ROUTE_NEG,
}


def main() -> int:
    data = json.loads((HERE / "router_cases.json").read_text())

    # ---- routing: real jev, same strings as production
    questions, expected = [], {}
    for kind, q in QUESTIONS.items():
        for i, case in enumerate(data[kind]):
            qid = f"{kind}:{i}"
            questions.append(Question(qid, route_text(q, case["candidate"]),
                                      route_state(case["claim"], case.get("context", ""))))
            expected[qid] = case["expected"]

    judge = JevJudge()
    verdicts = judge.ask(questions)

    per = defaultdict(lambda: {"n": 0, "correct": 0, "wrong": []})
    strong_touches = {"n": 0, "cleared": 0}  # of the true touches, how many pass the accusation bar
    for qid, want in expected.items():
        kind, idx = qid.rsplit(":", 1)
        v = verdicts[qid]
        got = v.p_yes >= MATCH_AT
        per[kind]["n"] += 1
        if got == want:
            per[kind]["correct"] += 1
        else:
            per[kind]["wrong"].append({"case": data[kind][int(idx)], "expected": want,
                                       "got": got, "p_yes": round(v.p_yes, 3)})
        if kind == "negative_touch" and want:
            strong_touches["n"] += 1
            strong_touches["cleared"] += int(v.p_yes >= NEG_CONTRADICT_AT)

    total_n = sum(k["n"] for k in per.values())
    total_ok = sum(k["correct"] for k in per.values())
    print(f"\nrouter smoke eval, {total_n} labeled cases, {total_ok} correct ({100 * total_ok / total_n:.1f}%)\n")
    for kind in QUESTIONS:
        r = per[kind]
        flag = "" if r["correct"] == r["n"] else "  <-- look here"
        print(f"  {kind:<18} {r['correct']:>2}/{r['n']}{flag}")
        for w in r["wrong"]:
            note = w["case"].get("note", "")
            print(f"      missed: expected {w['expected']}, got {w['got']} (p_yes {w['p_yes']}) {('[' + note + ']') if note else ''}")
    print(f"\n  negative_touch: of {strong_touches['n']} real touches, {strong_touches['cleared']} clear the "
          f"accusation bar (p >= {NEG_CONTRADICT_AT}) and would actually read CONTRADICTED")

    s = judge.stats
    print(f"\nmeasured: {s.questions} judgments, {s.calls} calls, {s.wall_seconds:.2f}s wall, "
          f"{s.input_tokens} tokens in, ${s.cost_usd:.6f}")

    # ---- classification: pure code, no jev, still worth a number
    cls = data["classification"]
    cls_ok, cls_wrong = 0, []
    for case in cls:
        got = classify(case["text"])
        if got == case["expected"]:
            cls_ok += 1
        else:
            cls_wrong.append({"case": case, "got": got})
    print(f"\nclassifier, {len(cls)} labeled sentences, {cls_ok} correct ({100 * cls_ok / len(cls):.1f}%)")
    for w in cls_wrong:
        note = w["case"].get("note", "")
        print(f"      missed: \"{w['case']['text']}\" expected {w['case']['expected']}, got {w['got']} {('[' + note + ']') if note else ''}")

    out = {
        "date": str(date.today()),
        "routing": {"total": {"n": total_n, "correct": total_ok},
                    "per_kind": {k: {"n": v["n"], "correct": v["correct"], "wrong": v["wrong"]} for k, v in per.items()},
                    "negative_touch_accusation_bar": strong_touches},
        "classification": {"n": len(cls), "correct": cls_ok, "wrong": cls_wrong},
        "stats": {"judgments": s.questions, "calls": s.calls, "wall_seconds": round(s.wall_seconds, 3),
                  "input_tokens": s.input_tokens, "output_tokens": s.output_tokens,
                  "cost_usd": round(s.cost_usd, 8)},
    }
    results_dir = HERE / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = results_dir / f"{date.today()}-router.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nwritten: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
