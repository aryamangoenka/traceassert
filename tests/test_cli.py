# cli smoke tests with an injected scripted judge, pytest never touches the
# network or spends a cent. the real report card gets golden tests at step 8.

from pathlib import Path

from traceassert.cli import main
from traceassert.judge import ScriptedJudge

FIXTURE = str(Path(__file__).parent / "fixtures" / "tiny_session.jsonl")


def test_usage_when_called_wrong():
    assert main([]) == 2
    assert main(["nope"]) == 2


def test_fail_finding_exits_one(capsys):
    judge = ScriptedJudge({"claim:0": (True, 0.9), "claim:1": (False, 0.97)})
    assert main(["test", FIXTURE], judge=judge) == 1
    out = capsys.readouterr().out
    assert "6 events" in out
    assert "FAIL [unsupported-claim]" in out


def test_clean_trace_exits_zero(capsys):
    judge = ScriptedJudge({"claim:0": (True, 0.9), "claim:1": (True, 0.9)})
    assert main(["test", FIXTURE], judge=judge) == 0
    assert "0 findings" in capsys.readouterr().out
