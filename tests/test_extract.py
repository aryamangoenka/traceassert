# known-answer tests for the extraction layer. deterministic in, exact out.

from traceassert.extract import extract_claims, extract_test_runs
from traceassert.models import AssistantMessage, CommandRun, Trace, UserMessage


def _trace(events):
    return Trace(path="fake", events=events)


def test_claims_come_from_final_message_only():
    trace = _trace([
        UserMessage(id=0, text="fix the thing"),
        AssistantMessage(id=1, text="tests pass so far."),  # mid-session, ignored in v0
        AssistantMessage(id=2, text="Refactored the parser. All tests pass now. Let me know if anything looks off."),
    ])
    claims = extract_claims(trace)
    assert [c.text for c in claims] == ["All tests pass now."]
    assert claims[0].event_id == 2


def test_over_extraction_is_fine_but_nonclaims_are_skipped():
    trace = _trace([
        AssistantMessage(id=0, text="Done! The fix works. Here is a haiku about parsers."),
    ])
    texts = [c.text for c in extract_claims(trace)]
    assert "Done!" in texts
    assert "The fix works." in texts
    assert "Here is a haiku about parsers." not in texts


def test_no_assistant_message_no_claims():
    assert extract_claims(_trace([UserMessage(id=0, text="hi")])) == []


def test_test_run_detection():
    trace = _trace([
        CommandRun(id=0, command="pytest -q", failed=True),
        CommandRun(id=1, command="ls -la"),
        CommandRun(id=2, command="npm test"),
        CommandRun(id=3, command="uv run pytest tests/"),
        CommandRun(id=4, command="git status"),
    ])
    assert [c.id for c in extract_test_runs(trace)] == [0, 2, 3]


def test_writing_a_test_file_is_not_running_tests():
    # dogfood find: a heredoc that WRITES test code contains the word pytest,
    # but only line one says what the command actually does
    trace = _trace([
        CommandRun(id=0, command="cat >> tests/test_cli.py <<'EOF'\ndef test_x():\n    pytest.raises(...)\nEOF"),
        CommandRun(id=1, command="pytest -q\n# comment"),
    ])
    assert [c.id for c in extract_test_runs(trace)] == [1]
