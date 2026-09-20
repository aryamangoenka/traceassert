# golden test: for this exact trace and these exact verdicts, the report must
# print exactly this. if a formatting change breaks it on purpose, regenerate
# the golden and let the diff tell the story in review.

from pathlib import Path

from traceassert.judge import ScriptedJudge
from traceassert.parser import parse_trace
from traceassert.report import render
from traceassert.rules import all_rules, run_rules

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_session.jsonl"
GOLDEN = Path(__file__).parent / "golden" / "tiny_session_report.txt"


def _report(answers):
    trace = parse_trace(FIXTURE)
    trace.path = "tests/fixtures/tiny_session.jsonl"  # machine-independent
    judge = ScriptedJudge(answers)
    questions, _, findings = run_rules(trace, judge, all_rules())
    return render(trace, questions, findings, color=False)


FULL_HOUSE = {
    "scope:2": (False, 0.9),
    "claim:0": (False, 0.89),
    "claim:1": (False, 0.99),
    "destr:3": (False, 0.95), "auth:3": (False, 0.8),
    "destr:4": (False, 0.95), "auth:4": (False, 0.8),
    "same:3:4": (True, 0.96), "newinfo:3:4": (False, 0.95),
    "summary:final": (True, 0.9),
}


def test_report_matches_golden():
    assert _report(FULL_HOUSE) + "\n" == GOLDEN.read_text()


def test_clean_report_says_passed():
    answers = dict(FULL_HOUSE)
    answers.update({"claim:0": (True, 0.9), "claim:1": (True, 0.9),
                    "newinfo:3:4": (True, 0.9)})
    out = _report(answers)
    assert "PASSED" in out
    assert "FAILED" not in out
    assert "✗" not in out


def test_reviews_never_say_failed():
    # only a review-bucket finding: the run needs a look, not a siren
    answers = dict(FULL_HOUSE)
    answers.update({"claim:1": (True, 0.9), "claim:0": (False, 0.75),
                    "newinfo:3:4": (True, 0.9)})
    out = _report(answers)
    # the evidence text may say FAILED (a failed command is the receipt),
    # what must be absent is the verdict header on its own line
    assert "\nFAILED\n" not in out
    assert "✗" not in out
    assert "NEEDS A HUMAN LOOK" in out
