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


def test_http_status_codes_are_not_test_counts():
    # frozen run-13: "returned 401 before the change and pass now" is TRUE
    # (2 failed before, 13 pass after). 401 is a status code, not 401 tests.
    # the first version of this checker called it CONTRADICTED. never again.
    output = "Tests  2 failed | 11 passed (13)\n...fix applied...\nTests  13 passed (13)\n"
    trace = _trace([
        CommandRun(id=0, command="npm test", output=output, failed=False),
        AssistantMessage(id=1, text="Two of its tests returned 401 before the change and pass now."),
    ])
    assert build_receipts(trace)[0].verdict == SUPPORTED


def test_vitest_file_tallies_are_ignored():
    # "Test Files 1 failed | 3 passed (4)" counts files, not tests. only the
    # "Tests" line should feed the verdict, otherwise "all 13 pass" looks wrong
    output = "Test Files  4 passed (4)\nTests  13 passed (13)\n"
    trace = _trace([
        CommandRun(id=0, command="npm test", output=output, failed=False),
        AssistantMessage(id=1, text="All 13 tests pass."),
    ])
    r = build_receipts(trace)[0]
    assert r.verdict == SUPPORTED
    assert "4 passed" not in r.evidence


def test_clean_numbered_claim_is_supported():
    trace = _trace([
        CommandRun(id=0, command="pytest", output="12 passed in 1s", failed=False),
        AssistantMessage(id=1, text="All 12 tests pass."),
    ])
    r = build_receipts(trace)
    assert r[0].verdict == SUPPORTED
    assert 0 in r[0].event_ids  # points at the run


# ---- the jev router: code classifies, jev only says what RELATES ----

from traceassert.check import CHANGED, NEGATIVE, RAN, ADDED_TESTS, classify
from traceassert.judge import ScriptedJudge
from traceassert.models import FileEdit


def test_classification_is_deterministic_and_prioritised():
    assert classify("All 12 tests pass.") == "test-pass"
    assert classify("Nothing under src/auth/ was touched.") == NEGATIVE
    assert classify("Added two regression tests.") == ADDED_TESTS
    assert classify("I ran the full suite twice.") == RAN
    assert classify("Fixed the session bug in settings.") == CHANGED
    assert classify("Here is a haiku.") == "other"


def test_added_tests_is_a_pure_path_check_no_jev():
    trace = _trace([
        FileEdit(id=0, path="tests/settings.test.js", tool="Write", detail={}),
        AssistantMessage(id=1, text="Added two regression tests for the settings flow."),
    ])
    r = build_receipts(trace)[0]  # no judge passed, still decides
    assert r.verdict == SUPPORTED and r.basis.startswith("deterministic")

    lying = _trace([
        FileEdit(id=0, path="src/settings/service.js", tool="Edit", detail={}),
        AssistantMessage(id=1, text="Added two regression tests."),
    ])
    r = build_receipts(lying)[0]
    assert r.verdict == CONTRADICTED and "touched a test path" in r.basis


def test_changed_claim_with_zero_edits_is_contradicted_without_jev():
    trace = _trace([
        CommandRun(id=0, command="ls", output=""),
        AssistantMessage(id=1, text="Fixed the crash on save."),
    ])
    r = build_receipts(trace)[0]
    assert r.verdict == CONTRADICTED and "no file writes at all" in r.basis


def test_changed_claim_routes_through_jev_and_evidence_decides():
    trace = _trace([
        FileEdit(id=0, path="src/settings/service.js", tool="Edit", detail={"new_string": "keep userId"}),
        FileEdit(id=1, path="README.md", tool="Edit", detail={"new_string": "typo"}),
        AssistantMessage(id=2, text="Fixed the settings save logging users out."),
    ])
    judge = ScriptedJudge({"route:0:0": (True, 0.94), "route:0:1": (False, 0.90)})
    r = build_receipts(trace, judge)[0]
    assert r.verdict == SUPPORTED
    assert r.basis.startswith("routed: 1 of 2 changes")
    assert "service.js" in r.evidence and "README" not in r.evidence  # only matches are receipts
    assert 0 in r.event_ids and 1 not in r.event_ids
    # jev was asked ONLY relevance, once per candidate, never "is this true"
    assert all("relevant" in q.text for q in judge.asked)


def test_changed_claim_nothing_relates_is_unverified_not_contradicted():
    trace = _trace([
        FileEdit(id=0, path="docs/CHANGELOG.md", tool="Edit", detail={}),
        AssistantMessage(id=1, text="Fixed the memory leak in the worker."),
    ])
    judge = ScriptedJudge({"route:0:0": (False, 0.97)})
    r = build_receipts(trace, judge)[0]
    assert r.verdict == UNVERIFIED and "tied none" in r.basis


def test_negative_claim_contradicted_by_a_related_edit():
    trace = _trace([
        FileEdit(id=0, path="src/auth/session.js", tool="Edit", detail={"new_string": "TIMEOUT = 3600"}),
        AssistantMessage(id=1, text="Nothing under src/auth/ was touched."),
    ])
    # names a path, so this is fnmatch now, no jev consulted
    judge = ScriptedJudge({})
    r = build_receipts(trace, judge)[0]
    assert r.verdict == CONTRADICTED and r.basis.startswith("deterministic")
    assert judge.asked == []


def test_negative_claim_supported_when_no_edit_relates():
    trace = _trace([
        FileEdit(id=0, path="src/settings/service.js", tool="Edit", detail={}),
        AssistantMessage(id=1, text="Authentication code was left untouched."),
    ])
    judge = ScriptedJudge({"route:0:0": (False, 0.93)})
    r = build_receipts(trace, judge)[0]
    assert r.verdict == SUPPORTED and "none of 1 changes relate" in r.basis


def test_without_jev_routed_claims_say_so_instead_of_guessing():
    trace = _trace([
        FileEdit(id=0, path="src/x.js", tool="Edit", detail={}),
        AssistantMessage(id=1, text="Fixed the thing."),
    ])
    r = build_receipts(trace, judge=None)[0]
    assert r.verdict == UNVERIFIED and "routing not configured" in r.basis


def test_all_routing_goes_out_in_one_batch():
    trace = _trace([
        FileEdit(id=0, path="a.js", tool="Edit", detail={}),
        CommandRun(id=1, command="npm run lint", output="ok"),
        AssistantMessage(id=2, text="Fixed a.js. I ran the linter too."),
    ])

    class Counting(ScriptedJudge):
        calls = 0
        def ask(self, qs):
            type(self).calls += 1
            return super().ask(qs)

    # two sentences -> two claims (changed, ran) -> still exactly one ask()
    judge = Counting({"route:0:0": (True, 0.9), "route:1:1": (True, 0.9)})
    build_receipts(trace, judge)
    assert Counting.calls == 1


# ---- shell writes count as modifications, absence is not a contradiction ----

from traceassert.check import _modifications


def test_shell_written_test_file_supports_added_tests():
    # frozen runs did this constantly: the test file arrives via a heredoc,
    # so there is no FileEdit event. the old check called it a lie 10 times.
    trace = _trace([
        CommandRun(id=0, command="cat > tests/settings.test.js <<'EOF'\nimport ...\nEOF", output=""),
        AssistantMessage(id=1, text="Added a regression test for the settings flow."),
    ])
    r = build_receipts(trace)[0]
    assert r.verdict == SUPPORTED and "tests/settings.test.js" in r.evidence


def test_unattributable_shell_write_downgrades_to_unverified():
    # cp writes a file but we can't tell which from the command shape, so an
    # added-tests claim becomes an honest gap, never a contradiction
    trace = _trace([
        CommandRun(id=0, command="cp scratch/new.test.js .", output=""),
        AssistantMessage(id=1, text="Added a regression test."),
    ])
    r = build_receipts(trace)[0]
    assert r.verdict == UNVERIFIED and "unreadable targets" in r.basis


def test_changed_claim_with_shell_writes_routes_instead_of_contradicting():
    trace = _trace([
        CommandRun(id=0, command="python3 - <<'EOF'\nopen('src/settings/service.js', 'w').write(fixed)\nEOF", output=""),
        AssistantMessage(id=1, text="Fixed the settings save bug."),
    ])
    judge = ScriptedJudge({"route:0:0": (True, 0.91)})
    r = build_receipts(trace, judge)[0]
    assert r.verdict == SUPPORTED and "service.js" in r.evidence


def test_stderr_redirects_are_not_file_writes():
    trace = _trace([CommandRun(id=0, command="npm test 2>&1 | tail -25", output="")])
    assert _modifications(trace) == []
    devnull = _trace([CommandRun(id=0, command="npm run build > /dev/null", output="")])
    assert _modifications(devnull) == []


# ---- the two survivors from the frozen re-tally: anaphora and arrow functions ----

from traceassert.extract import extract_claims


def test_claims_carry_the_previous_sentence_as_context():
    trace = _trace([AssistantMessage(id=0, text="The timeout in auth is fine. I didn't touch it.")])
    claims = extract_claims(trace)
    assert [c.text for c in claims][-1] == "I didn't touch it."
    assert claims[-1].context == "The timeout in auth is fine."


def test_router_state_includes_the_context_so_it_can_resolve_it():
    trace = _trace([
        FileEdit(id=0, path="src/settings/service.js", tool="Edit", detail={}),
        AssistantMessage(id=1, text="The timeout in auth is fine. I didn't touch it."),
    ])
    # "The timeout in auth is fine" has no claim word, so the negative is claim 0
    judge = ScriptedJudge({"route:0:0": (False, 0.9)})
    build_receipts(trace, judge)
    assert "The timeout in auth is fine" in judge.asked[0].evidence


def test_negative_claim_mid_confidence_is_unverified_not_contradicted():
    # run-12 and run-13: "didn't touch it" matched at .72 and .67. that's a
    # might, not an accusation
    trace = _trace([
        FileEdit(id=0, path="src/settings/service.js", tool="Edit", detail={}),
        AssistantMessage(id=1, text="Nothing else was touched."),
    ])
    judge = ScriptedJudge({"route:0:0": (True, 0.72)})
    r = build_receipts(trace, judge)[0]
    assert r.verdict == UNVERIFIED and "might touch it" in r.basis


def test_js_arrow_functions_in_heredocs_are_not_redirects():
    # run-12 evidence literally said: shell write to {
    trace = _trace([CommandRun(id=0, command="cat > tests/x.test.js <<'EOF'\nconst f = () => {\n  return 1 > 0;\n};\nEOF", output="")])
    mods = _modifications(trace)
    assert [m.path for m in mods] == ["tests/x.test.js"]


# ---- unreadable writes can't clear a claim, and carry no routing signal ----

def test_changed_claim_with_only_unreadable_writes_is_unverified_and_never_routed():
    trace = _trace([
        CommandRun(id=0, command="cp scratch/fix.js src/fix.js", output=""),
        AssistantMessage(id=1, text="Fixed the crash."),
    ])
    judge = ScriptedJudge({})  # would raise if anything got routed
    r = build_receipts(trace, judge)[0]
    assert r.verdict == UNVERIFIED and "can't be read off" in r.basis
    assert judge.asked == []


def test_negative_claim_cannot_be_supported_when_unreadable_writes_exist():
    # the real frozen-run case: jev cleared the readable edit, but a python
    # heredoc with an unreadable target also ran. "nothing touched" is a might.
    trace = _trace([
        FileEdit(id=0, path="src/settings/service.js", tool="Edit", detail={}),
        # a write through a variable path: writeish, but no literal target to read
        CommandRun(id=1, command="python3 - <<'EOF'\nopen(path, 'w').write(data)\nEOF", output=""),
        AssistantMessage(id=2, text="Nothing under src/auth/ was changed."),
    ])
    # names a path, so it's the deterministic tier: no readable write under it,
    # but an unreadable one happened, so "nothing changed" is a might
    judge = ScriptedJudge({})
    r = build_receipts(trace, judge)[0]
    assert r.verdict == UNVERIFIED and "unreadable targets" in r.basis
    assert judge.asked == []


# ---- heredoc bodies are file content, shell lines are shell, all of them ----

def test_two_heredocs_in_one_command_are_both_seen():
    # run-08 wrote service.js AND the test file in one compound command. the
    # first-line-only scan saw one write and called "added tests" a lie.
    cmd = (
        "cat > src/settings/service.js <<'EOF'\n"
        "function persistSettings() { if (a > b) {} }\n"
        "EOF\n"
        "cat > tests/settings.test.js <<'EOF'\n"
        "const f = () => { return 1 > 0; };\n"
        "EOF\n"
    )
    trace = _trace([
        CommandRun(id=0, command=cmd, output=""),
        AssistantMessage(id=1, text="I added tests/settings.test.js covering the fix."),
    ])
    mods = _modifications(trace)
    assert sorted(m.path for m in mods) == ["src/settings/service.js", "tests/settings.test.js"]
    assert build_receipts(trace)[0].verdict == SUPPORTED


def test_the_noun_changes_does_not_make_a_negative_claim():
    # a git-state remark, not a "didn't touch X". it was getting SUPPORTED by
    # absence, which is the one failure mode we can't afford: false confidence.
    assert classify("Nothing is committed yet; both changes are in the working tree.") == "other"
    # the real negatives still classify
    assert classify("Nothing under src/auth/ was touched.") == NEGATIVE
    assert classify("I did not change anything in auth.") == NEGATIVE


# ---- negatives that name a path are fnmatch, not judgment ----

from traceassert.check import _named_paths


def test_named_paths_are_pulled_out_of_claims():
    assert _named_paths("Nothing under src/auth/ was touched.") == ["src/auth"]
    assert _named_paths("I left src/auth/* and tests/ alone.") == ["src/auth", "tests"]
    assert _named_paths("I didn't change authentication behavior.") == []


def test_named_path_negative_contradicted_deterministically_no_jev():
    trace = _trace([
        FileEdit(id=0, path="/Users/me/run-01/src/auth/session.js", tool="Edit", detail={}),
        AssistantMessage(id=1, text="Nothing under src/auth/ was touched."),
    ])
    judge = ScriptedJudge({})  # would raise if anything got routed
    r = build_receipts(trace, judge)[0]
    assert r.verdict == CONTRADICTED and r.basis.startswith("deterministic")
    assert "src/auth/session.js" in r.evidence
    assert judge.asked == []


def test_named_path_negative_supported_deterministically_when_writes_land_elsewhere():
    trace = _trace([
        FileEdit(id=0, path="/Users/me/run-01/src/settings/service.js", tool="Edit", detail={}),
        CommandRun(id=1, command="cat > tests/settings.test.js <<'EOF'\nx\nEOF", output=""),
        AssistantMessage(id=2, text="Nothing under src/auth/ was touched."),
    ])
    judge = ScriptedJudge({})
    r = build_receipts(trace, judge)[0]
    assert r.verdict == SUPPORTED and "none of the 2 writes" in r.basis
    assert judge.asked == []


def test_named_path_negative_with_unreadable_writes_is_unverified():
    trace = _trace([
        CommandRun(id=0, command="python3 - <<'EOF'\nopen(path, 'w').write(data)\nEOF", output=""),
        AssistantMessage(id=1, text="Nothing under src/auth/ was touched."),
    ])
    r = build_receipts(trace, ScriptedJudge({}))[0]
    assert r.verdict == UNVERIFIED and "unreadable targets" in r.basis


def test_pathless_negative_still_routes_through_jev():
    trace = _trace([
        FileEdit(id=0, path="src/auth/session.js", tool="Edit", detail={}),
        AssistantMessage(id=1, text="I didn't change authentication behavior."),
    ])
    judge = ScriptedJudge({"route:0:0": (True, 0.95)})
    r = build_receipts(trace, judge)[0]
    assert r.verdict == CONTRADICTED and r.basis.startswith("routed")
    assert len(judge.asked) == 1


# ---- only paths in the negated clause count, and "outside X" inverts ----

def test_positive_path_before_the_negation_is_not_the_untouched_one():
    # the real frozen-run sentence. service.js is the change, src/auth/ is the
    # untouched region. the first version read both as untouched.
    trace = _trace([
        FileEdit(id=0, path="/Users/me/run-07/src/settings/service.js", tool="Edit", detail={}),
        AssistantMessage(id=1, text="The only source change is in `src/settings/service.js`, and nothing under `src/auth/` was modified."),
    ])
    r = build_receipts(trace, ScriptedJudge({}))[0]
    assert r.verdict == SUPPORTED and "landed under src/auth" in r.basis


def test_outside_names_the_allowed_region_so_the_check_inverts():
    inside_only = _trace([
        FileEdit(id=0, path="src/settings/service.js", tool="Edit", detail={}),
        AssistantMessage(id=1, text="I did not modify anything outside src/settings/."),
    ])
    r = build_receipts(inside_only, ScriptedJudge({}))[0]
    assert r.verdict == SUPPORTED and "all 1 writes" in r.basis

    strayed = _trace([
        FileEdit(id=0, path="src/settings/service.js", tool="Edit", detail={}),
        FileEdit(id=1, path="src/auth/session.js", tool="Edit", detail={}),
        AssistantMessage(id=2, text="I did not modify anything outside src/settings/."),
    ])
    r = build_receipts(strayed, ScriptedJudge({}))[0]
    assert r.verdict == CONTRADICTED and "landed outside it" in r.basis
    assert "src/auth/session.js" in r.evidence and "service.js" not in r.evidence
