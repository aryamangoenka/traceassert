# the judge. rules never talk to jev directly, they hand Questions to a judge
# and get Verdicts back. two judges exist: ScriptedJudge for tests (no
# network, no cost, deterministic) and JevJudge for the real thing. batching
# philosophy: jev takes one state + many questions per call, so we group
# questions by shared evidence. each call's state contains ONLY that group's
# evidence, because accuracy decays with irrelevant state (jevtown finding).

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Question:
    qid: str
    text: str  # the single-hop yes/no instruction
    evidence: str  # the raw trace material it judges from, nothing else


@dataclass
class Verdict:
    # a noul answer is one number, p(yes). we keep it raw for calibration
    # later, and derive yes + confidence-in-that-direction from it.
    # confidence is NOT probability of truth (see contract).
    yes: bool
    confidence: float  # p if yes, 1-p if no
    p_yes: float = 0.0  # the raw noul value, untouched


@dataclass
class JudgeStats:
    calls: int = 0
    questions: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    wall_seconds: float = 0.0

    @property
    def cost_usd(self) -> float:
        # $0.042 per million input tokens, output free
        # (docs.typesafe.ai pricing, as of 2026-09-20)
        return self.input_tokens * 0.042 / 1_000_000


class ScriptedJudge:
    """you script the answers, so rule composition is testable without jev."""

    def __init__(self, answers: dict[str, tuple[bool, float]]):
        self.answers = answers  # qid -> (yes, confidence)
        self.asked: list[Question] = []
        self.stats = JudgeStats()

    def ask(self, questions: list[Question]) -> dict[str, Verdict]:
        self.asked.extend(questions)
        self.stats.questions += len(questions)
        out = {}
        for q in questions:
            if q.qid not in self.answers:
                raise KeyError(f"scripted judge has no answer for {q.qid}, test is incomplete")
            yes, conf = self.answers[q.qid]
            out[q.qid] = Verdict(yes=yes, confidence=conf, p_yes=conf if yes else 1 - conf)
        return out


def group_by_evidence(questions: list[Question]) -> list[list[Question]]:
    # questions sharing the exact same evidence ride in one api call
    groups: dict[str, list[Question]] = {}
    for q in questions:
        groups.setdefault(q.evidence, []).append(q)
    return list(groups.values())


def _load_dotenv() -> None:
    # tiny .env reader so nobody pastes keys into shells or chats. tolerant of
    # `export`, spaces around =, and quotes. we also map JEV_API_KEY to the
    # TYPESAFE_API_KEY name the sdk wants.
    env = Path(".env")
    if env.is_file():
        for line in env.read_text().splitlines():
            m = re.match(r"^\s*(?:export\s+)?(\w+)\s*=\s*['\"]?(.*?)['\"]?\s*$", line)
            if m and m.group(1) not in os.environ:
                os.environ[m.group(1)] = m.group(2)
    if "TYPESAFE_API_KEY" not in os.environ and "JEV_API_KEY" in os.environ:
        os.environ["TYPESAFE_API_KEY"] = os.environ["JEV_API_KEY"]


class JevJudge:
    """the real one. talks to jev through typesafe's sdk, batched by evidence."""

    def __init__(self, model: str = "jev-latest"):
        _load_dotenv()
        if "TYPESAFE_API_KEY" not in os.environ:
            raise RuntimeError("no jev key: put JEV_API_KEY=... in .env (it stays gitignored)")
        from typesafe_sdk import TypeSafeClient  # import here so tests never need it

        self.client = TypeSafeClient()
        self.model = model
        self.stats = JudgeStats()

    def ask(self, questions: list[Question]) -> dict[str, Verdict]:
        from typesafe_sdk import Noul

        out: dict[str, Verdict] = {}
        for group in group_by_evidence(questions):
            # api question keys need to be plain names, our qids have colons,
            # so we alias q0, q1... and map back after
            alias = {f"q{i}": q for i, q in enumerate(group)}
            t0 = time.perf_counter()
            response = self.client.system_one(
                state=group[0].evidence,
                questions={k: Noul(instructions=q.text) for k, q in alias.items()},
            )
            self.stats.wall_seconds += time.perf_counter() - t0
            self.stats.calls += 1
            self.stats.questions += len(group)
            usage = getattr(response, "usage", None)
            if usage is not None:
                self.stats.input_tokens += getattr(usage, "input_tokens", 0) or 0
                self.stats.output_tokens += getattr(usage, "output_tokens", 0) or 0

            for k, q in alias.items():
                p = float(response.answers[k].noul)
                yes = p >= 0.5
                out[q.qid] = Verdict(yes=yes, confidence=p if yes else 1 - p, p_yes=p)
        return out
