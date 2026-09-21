# deterministic claim-checker tests. no jev, no scripted judge, the numbers
# decide, so these are plain known-answer tests. the two headline cases:
# the 393/394 contradiction (the demo) and the stash false-positive that the
# old rule got wrong (must be SUPPORTED now).

from traceassert.check import (
    CONTRADICTED,
    SUPPORTED,
    UNVERIFIED,
    build_receipts,
)
from traceassert.models import AssistantMessage, CommandRun, Trace, UserMessage


def _trace(events):
    return Trace(path="fake", events=events)


def test_the_393_394_contradiction():
    # the real zerodha catch, distilled: agent claims 394, trace shows 393
    trace = _trace([
        UserMessage(id=0, text="add a test and run the suite"),
        CommandRun(id=1, command="pytest -q", output="393 passed in 6.2s", failed=False),
        AssistantMessage(id=2, text="One new test (394 total); all tests pass."),
    ])
    r = build_receipts(trace)
    assert len(r) == 1
    assert r[0].verdict == CONTRADICTED
    assert "394" in r[0].basis and "393" in r[0].basis


def test_stash_false_positive_is_now_supported():
    # the frozen-run trap: one compound command runs tests clean (12), then
    # stashes the fix and reruns (2 fail) to prove the regression test bites,
    # then pops. claim "all 12 tests pass" must be SUPPORTED, the failing run
    # is a different repo state and must not contradict.
    output = (
        "Tests  12 passed (12)\n"
        "... stashed the fix ...\n"
        "Tests  2 failed | 10 passed (12)\n"
        "... popped ...\n"
    )
    trace = _trace([
        UserMessage(id=0, text="fix the bug and add a regression test"),
        CommandRun(id=1, command="npm test && git stash && npm test && git stash pop", output=output, failed=False),
        AssistantMessage(id=2, text="All 12 tests pass, including the new regression test."),
    ])
    r = build_receipts(trace)
    assert r[0].verdict == SUPPORTED
    assert "12 passed" in r[0].evidence


def test_all_pass_with_no_clean_run_is_contradicted():
    trace = _trace([
        CommandRun(id=0, command="pytest", output="3 failed, 41 passed", failed=True),
        AssistantMessage(id=1, text="All tests pass now."),
    ])
    assert build_receipts(trace)[0].verdict == CONTRADICTED


def test_test_claim_with_no_test_run_is_unverified():
    trace = _trace([
        CommandRun(id=0, command="ls -la", output="files", failed=False),
        AssistantMessage(id=1, text="All tests pass."),
    ])
    r = build_receipts(trace)
    assert r[0].verdict == UNVERIFIED
    assert "no test output" in r[0].basis


def test_non_test_claim_is_unverified_for_now():
    # step 1 only knows test claims. a deploy claim is honestly a gap, not a lie
    trace = _trace([
        CommandRun(id=0, command="pytest", output="5 passed", failed=False),
        AssistantMessage(id=1, text="Deployed to production successfully."),
    ])
    verdicts = {r.claim: r.verdict for r in build_receipts(trace)}
    # "Deployed... successfully" has no test word, so it's unverified
    assert verdicts["Deployed to production successfully."] == UNVERIFIED


def test_clean_numbered_claim_is_supported():
    trace = _trace([
        CommandRun(id=0, command="pytest", output="12 passed in 1s", failed=False),
        AssistantMessage(id=1, text="All 12 tests pass."),
    ])
    r = build_receipts(trace)
    assert r[0].verdict == SUPPORTED
    assert 0 in r[0].event_ids  # points at the run
