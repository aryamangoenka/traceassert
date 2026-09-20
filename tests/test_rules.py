# rule composition tests with a scripted judge: we're testing OUR logic
# (narrowing + composition + buckets), not jev's judgment. jev's own accuracy
# gets measured by the smoke eval (step 7), different job.

from pathlib import Path

from traceassert.judge import ScriptedJudge, group_by_evidence, Question
from traceassert.parser import parse_trace
from traceassert.rules import run_rules

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_session.jsonl"
# the fixture's final message is "fixed the redirect. all tests pass now."
# which extracts two claims, and its pytest runs both failed


def test_unsupported_claim_becomes_a_fail_finding():
    trace = parse_trace(FIXTURE)
    judge = ScriptedJudge({
        "claim:0": (True, 0.80),   # "fixed the redirect." plausibly supported
        "claim:1": (False, 0.97),  # "all tests pass now." contradicted, high confidence
    })
    _, _, findings = run_rules(trace, judge)

    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "unsupported-claim"
    assert f.status == "FAIL"
    assert f.confidence == 0.97
    assert "all tests pass now." in f.summary
    assert "pytest -q" in f.evidence  # receipts attached
    assert 5 in f.event_ids and 3 in f.event_ids  # the claim message + a test run


def test_buckets_review_and_no_finding():
    trace = parse_trace(FIXTURE)
    # same unsupported verdicts, lower confidences
    judge = ScriptedJudge({"claim:0": (False, 0.72), "claim:1": (False, 0.41)})
    _, _, findings = run_rules(trace, judge)
    assert [f.status for f in findings] == ["REVIEW"]  # 0.72 -> REVIEW, 0.41 -> dropped


def test_supported_claims_produce_nothing():
    trace = parse_trace(FIXTURE)
    judge = ScriptedJudge({"claim:0": (True, 0.95), "claim:1": (True, 0.95)})
    _, _, findings = run_rules(trace, judge)
    assert findings == []


def test_questions_share_one_evidence_group():
    # both claims judge against the same test-run evidence, so the jev judge
    # would send exactly one api call for them
    trace = parse_trace(FIXTURE)
    judge = ScriptedJudge({"claim:0": (True, 0.9), "claim:1": (True, 0.9)})
    questions, _, _ = run_rules(trace, judge)
    assert len(questions) == 2
    assert len(group_by_evidence(questions)) == 1


def test_grouping_splits_different_evidence():
    qs = [
        Question(qid="a", text="t", evidence="E1"),
        Question(qid="b", text="t", evidence="E2"),
        Question(qid="c", text="t", evidence="E1"),
    ]
    groups = group_by_evidence(qs)
    assert [[q.qid for q in g] for g in groups] == [["a", "c"], ["b"]]
