# the extraction layer: deterministic narrowing between the IR (pure facts)
# and the rules. a Claim is an interpretation of a sentence, that's exactly
# why it lives here and not in models.py. philosophy: over-extract candidates
# and let the rule + judge filter, a missed claim is an invisible false
# negative and those are the scary ones (the smoke eval measures this).

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import AssistantMessage, CommandRun, Trace


@dataclass
class Claim:
    text: str
    event_id: int  # which AssistantMessage it came from, findings point back here


# success/status flavored words. this is hacky regex extraction, a jev Choice
# call could classify sentences properly later, fix in v1
CLAIMY = re.compile(
    r"\b(pass|passes|passed|passing|fixed|works|working|done|complete|completed|success|succeeded|green|resolved|deployed|verified)\b",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def extract_claims(trace: Trace) -> list[Claim]:
    # v0 scope decision: claims come from the FINAL assistant message only,
    # that's the "done!" the human actually reads. widening to mid-session
    # claims is a v1 item.
    final = None
    for e in reversed(trace.events):
        if isinstance(e, AssistantMessage):
            final = e
            break
    if final is None:
        return []

    claims = []
    for sentence in _SENTENCE_SPLIT.split(final.text):
        sentence = sentence.strip().strip("-*# ").strip()
        if sentence and CLAIMY.search(sentence):
            claims.append(Claim(text=sentence, event_id=final.id))
    return claims


# commands that look like test runs. list is honestly incomplete, grows as
# dogfooding finds runners we missed
TESTY = re.compile(
    r"\b(pytest|jest|vitest|rspec|tox|unittest|cargo test|go test|make test|"
    r"npm (run )?test\w*|yarn test|pnpm (run )?test|uv run pytest|bun test)\b"
)


def extract_test_runs(trace: Trace) -> list[CommandRun]:
    # match on the first line only. dogfooding found a `cat >> test_x.py <<EOF`
    # whose heredoc BODY contained "pytest", which made writing a test file
    # count as running the tests. the command itself lives on line one.
    return [c for c in trace.command_runs if TESTY.search(c.command.split("\n", 1)[0])]
