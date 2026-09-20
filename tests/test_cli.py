# cli smoke tests with an injected scripted judge, pytest never touches the
# network or spends a cent. the real report card gets golden tests at step 8.
# all five rules run in the cli, so the script answers every question the
# fixture generates.

from pathlib import Path

from traceassert.cli import main
from traceassert.judge import ScriptedJudge

FIXTURE = str(Path(__file__).parent / "fixtures" / "tiny_session.jsonl")

# the fixture generates: 1 scope question (the app.py edit), 2 claims,
# 2 commands x (destr + auth), 1 repeat pair, 1 summary = 10 questions
EVERYTHING_FINE = {
    "scope:2": (False, 0.9),
    "claim:0": (True, 0.9), "claim:1": (True, 0.9),
    "destr:3": (False, 0.95), "auth:3": (False, 0.8),
    "destr:4": (False, 0.95), "auth:4": (False, 0.8),
    "same:3:4": (True, 0.9), "newinfo:3:4": (True, 0.9),
    "summary:final": (True, 0.9),
}


def test_usage_when_called_wrong():
    assert main([]) == 2
    assert main(["nope"]) == 2


def test_clean_trace_exits_zero(capsys):
    judge = ScriptedJudge(dict(EVERYTHING_FINE))
    assert main(["test", FIXTURE], judge=judge) == 0
    assert "0 findings" in capsys.readouterr().out


def test_fail_finding_exits_one(capsys):
    answers = dict(EVERYTHING_FINE)
    answers["claim:1"] = (False, 0.97)  # "all tests pass now." unsupported
    judge = ScriptedJudge(answers)
    assert main(["test", FIXTURE], judge=judge) == 1
    out = capsys.readouterr().out
    assert "6 events" in out
    assert "FAIL [unsupported-claim]" in out


def test_prohibit_glob_turns_scope_deterministic(capsys):
    # with app.py prohibited, the scope question disappears and tier 1 fires
    answers = dict(EVERYTHING_FINE)
    del answers["scope:2"]
    judge = ScriptedJudge(answers)
    assert main(["test", FIXTURE, "--prohibit", "app.py"], judge=judge) == 1
    out = capsys.readouterr().out
    assert "FAIL [scope] 1.00" in out
    assert "prohibited pattern" in out
