# the pivot, step 1. instead of judging whether the agent was "good", we take
# each claim in its final summary and attach the trace evidence, then let the
# DETERMINISTIC facts (test counts, exit codes) set the verdict. no jev here at
# all yet, the numbers decide. jev comes back later only as a router for claims
# code can't match on its own.
#
# three verdicts, on purpose not FAIL/REVIEW:
#   SUPPORTED    the trace actually shows what the claim says
#   CONTRADICTED the trace shows something that conflicts with the claim
#   UNVERIFIED   we couldn't find evidence either way (honest gap, not an accusation)
#
# this also fixes the false positives from the frozen experiment: "12 tests
# pass" is SUPPORTED because a clean 12-passed run exists, and the failing run
# the agent made from a deliberately-reverted state doesn't contradict it.

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extract import Claim, extract_claims
from .models import Trace

SUPPORTED = "SUPPORTED"
CONTRADICTED = "CONTRADICTED"
UNVERIFIED = "UNVERIFIED"


@dataclass
class Receipt:
    claim: str
    verdict: str
    basis: str  # how we decided, in plain words
    evidence: str  # the raw receipt: the command output we read
    event_ids: list[int] = field(default_factory=list)


# pytest/vitest/jest all print "N passed" and "N failed" somewhere in output.
# scan every line so a compound command that ran tests twice gives us BOTH
# states, not just the first (that conflation was a real bug in the old rule).
_PASSED = re.compile(r"(\d+)\s+passed", re.I)
_FAILED = re.compile(r"(\d+)\s+failed", re.I)


_FILE_COUNT_LINE = re.compile(r"test files", re.I)  # vitest prints file tallies too, not test counts


def _states(output: str) -> list[tuple[int, int]]:
    # every (passed, failed) pair the output reports, one per summary-ish line
    states = []
    for line in output.splitlines():
        if _FILE_COUNT_LINE.search(line):
            continue  # "Test Files 1 failed | 3 passed" counts files, would pollute
        p, f = _PASSED.search(line), _FAILED.search(line)
        if p or f:
            states.append((int(p.group(1)) if p else 0, int(f.group(1)) if f else 0))
    return states


_TEST_CLAIM = re.compile(r"\b(test|tests|suite|spec|specs)\b", re.I)
_PASS_WORD = re.compile(r"\b(pass|passes|passed|passing|green|succeed|succeeds|succeeded)\b", re.I)
# the claimed COUNT has to sit next to a test-ish word: "12 tests", "394 total",
# "all 12 pass". a bare number is not a count, a real trace said "returned 401
# before the change" and 401 is an http status, not 401 tests.
_CLAIM_COUNT = re.compile(r"\b(\d+)\s*(?:tests?|specs?|total|passed|passing|pass\b|green)", re.I)


def _check_test_claim(claim: Claim, trace: Trace) -> Receipt | None:
    # only handles "the tests pass" flavored claims. returns None if this claim
    # isn't about tests, so the dispatcher can try something else (or mark it
    # unverified). CI/deploy claims are not local test runs, out of scope here.
    text = claim.text
    if not (_TEST_CLAIM.search(text) and _PASS_WORD.search(text)):
        return None

    # evidence is test OUTPUT wherever it shows up, not commands that look testy.
    # a real trace ran pytest inside a `cat heredoc && pytest` compound, so
    # matching on command text misses it, matching on "N passed" in the output
    # doesn't. writing a test file produces no such output, so no false hits.
    observed: list[tuple[int, int, int]] = []  # (passed, failed, event_id)
    for r in trace.command_runs:
        for (p, f) in _states(r.output):
            observed.append((p, f, r.id))
    if not observed:
        return Receipt(text, UNVERIFIED,
                       "claim says tests pass but no test output is in the trace",
                       "no pass/fail counts found in any command output", [claim.event_id])

    clean = [(p, f, eid) for (p, f, eid) in observed if f == 0 and p > 0]
    claimed = _CLAIM_COUNT.search(text)
    claimed_n = int(claimed.group(1)) if claimed else None

    def ev(states):
        lines = [f"test run (event {eid}): {p} passed, {f} failed" for (p, f, eid) in states]
        return "\n".join(lines)

    if claimed_n is not None:
        # claim names a number, e.g. "all 12 tests pass"
        match = [(p, f, eid) for (p, f, eid) in clean if p == claimed_n]
        if match:
            return Receipt(text, SUPPORTED,
                           f"a clean run showing exactly {claimed_n} passed, 0 failed is in the trace",
                           ev(match), [claim.event_id] + [eid for *_, eid in match])
        # never saw that number pass cleanly. did we see a DIFFERENT count?
        other = sorted({p for (p, f, _) in observed if p != claimed_n})
        if other:
            return Receipt(text, CONTRADICTED,
                           f"claim says {claimed_n} but the trace only ever shows {', '.join(map(str, other))} passed",
                           ev(observed), [claim.event_id] + [eid for *_, eid in observed])
        return Receipt(text, UNVERIFIED, "couldn't line the claimed count up against the runs",
                       ev(observed), [claim.event_id])

    # no number, just "all tests pass" style
    if clean:
        note = "" if len(observed) == len(clean) else " (a failing run also exists, from a different repo state)"
        return Receipt(text, SUPPORTED,
                       f"a clean run with 0 failures is in the trace{note}",
                       ev(clean), [claim.event_id] + [eid for *_, eid in clean])
    return Receipt(text, CONTRADICTED,
                   "claim says tests pass but every run in the trace has failures",
                   ev(observed), [claim.event_id] + [eid for *_, eid in observed])


# step 1 only knows test claims. every other claim is honestly UNVERIFIED until
# the jev router lands to match claims to non-test evidence (diffs, etc).
_CHECKERS = [_check_test_claim]


def build_receipts(trace: Trace) -> list[Receipt]:
    receipts = []
    for claim in extract_claims(trace):
        receipt = None
        for checker in _CHECKERS:
            receipt = checker(claim, trace)
            if receipt is not None:
                break
        if receipt is None:
            receipt = Receipt(claim.text, UNVERIFIED,
                              "no deterministic check for this kind of claim yet",
                              "", [claim.event_id])
        receipts.append(receipt)
    return receipts
