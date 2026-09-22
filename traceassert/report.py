# the report card. contradiction-first: what the agent said, then what the
# trace proves. every verdict ships with its confidence and its receipts,
# never just a red X (docs/contract.md). this output IS the product's face,
# the launch gif is literally this scrolling by.

from __future__ import annotations

import os
import sys

from .extract import extract_claims
from .judge import JudgeStats, Question
from .models import Trace
from .rules import Finding

HEADERS = {
    "scope": "SCOPE VIOLATION",
    "unsupported-claim": "UNSUPPORTED CLAIM",
    "destructive-without-authorization": "UNAUTHORIZED DESTRUCTIVE ACTION",
    "repeated-failed-action": "REPEATED FAILED ACTION",
    "final-summary-accuracy": "SUMMARY MISMATCH",
}

# ansi, kept boring on purpose. color only when a human is watching.
RED, YELLOW, GREEN, DIM, BOLD, RESET = "\033[31m", "\033[33m", "\033[32m", "\033[2m", "\033[1m", "\033[0m"


def want_color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _clip(text: str, max_lines: int = 10) -> list[str]:
    lines = text.splitlines()
    if len(lines) > max_lines:
        return lines[:max_lines] + [f"... ({len(lines) - max_lines} more lines in the trace)"]
    return lines


def _finding_block(f: Finding, mark: str, c) -> list[str]:
    header = HEADERS.get(f.rule_id, f.rule_id.upper())
    pct = f"{round(f.confidence * 100)}%"
    out = [f"{mark} {c(BOLD)}{header}{c(RESET)}{' ' * max(1, 46 - len(header))}{pct}", ""]
    out.append(f"  {f.summary}")
    out.append("")
    out += [f"  {c(DIM)}{line}{c(RESET)}" for line in _clip(f.evidence)]
    out.append(f"  {c(DIM)}(events {f.event_ids}){c(RESET)}")
    out.append("")
    return out


def render(trace: Trace, questions: list[Question], findings: list[Finding],
           color: bool | None = None) -> str:
    color = want_color() if color is None else color
    c = (lambda code: code) if color else (lambda code: "")

    fails = [f for f in findings if f.status == "FAIL"]
    reviews = [f for f in findings if f.status == "REVIEW"]

    lines = [f"{c(DIM)}trace: {trace.path}{c(RESET)}"]
    if trace.user_request:
        req = trace.user_request.replace("\n", " ")
        lines.append(f'{c(DIM)}request: "{req[:120]}"{c(RESET)}')
    lines.append("")

    # what the agent said, verbatim from the trace, as it presented things
    claims = extract_claims(trace)
    if claims:
        lines.append("the agent said:")
        for claim in claims[:6]:
            lines.append(f'  {c(GREEN)}✓{c(RESET)} "{claim.text}"')
        lines.append("")

    checks = len(questions) + sum(1 for f in findings if f.confidence == 1.0)
    lines.append(f"{len(trace.events)} events · {checks} checks")
    lines.append("")

    if not findings:
        lines.append(f"{c(GREEN)}{c(BOLD)}PASSED{c(RESET)}  the trace backs up the story")
        return "\n".join(lines)

    if fails:
        lines.append(f"{c(RED)}{c(BOLD)}FAILED{c(RESET)}")
        lines.append("")
        for f in fails:
            lines += _finding_block(f, f"{c(RED)}✗{c(RESET)}", c)

    if reviews:
        lines.append(f"{c(YELLOW)}{c(BOLD)}NEEDS A HUMAN LOOK{c(RESET)}  {c(DIM)}(confidence .60 to .90){c(RESET)}")
        lines.append("")
        for f in reviews:
            lines += _finding_block(f, f"{c(YELLOW)}?{c(RESET)}", c)

    lines.append("─" * 54)
    tally = f"{len(trace.events)} events · {checks} checks · {len(fails)} violations"
    if reviews:
        tally += f" · {len(reviews)} for review"
    lines.append(tally)
    return "\n".join(lines)


def render_stats(stats: JudgeStats, color: bool | None = None) -> str:
    color = want_color() if color is None else color
    c = (lambda code: code) if color else (lambda code: "")
    return (f"{c(DIM)}{stats.questions} judgments · {stats.calls} calls · "
            f"{stats.wall_seconds:.2f}s · ${stats.cost_usd:.6f}{c(RESET)}")


# the check command's output: claim-anchored, not violation-anchored. every claim
# the agent made, with the evidence and a three-way verdict. deterministic first,
# jev only routes relevance.
_MARKS = {"SUPPORTED": ("✓", "GREEN"), "CONTRADICTED": ("✗", "RED"), "UNVERIFIED": ("?", "YELLOW")}
_COLORS = {"GREEN": GREEN, "RED": RED, "YELLOW": YELLOW}


def render_receipts(trace: Trace, receipts, color: bool | None = None, mode: str = "") -> str:
    # mode is one line of truth about jev: on, off because no key, or off by
    # --offline. without it a run with a key but no routed claims prints no
    # stats line and nobody can tell whether jev was even available.
    color = want_color() if color is None else color
    c = (lambda code: code) if color else (lambda code: "")

    lines = [f"{c(DIM)}trace: {trace.path}{c(RESET)}"]
    if trace.user_request:
        lines.append(f'{c(DIM)}request: "{trace.user_request.replace(chr(10), " ")[:100]}"{c(RESET)}')
    lines.append("")
    if mode:
        lines.insert(len(lines) - 1, f"{c(DIM)}jev routing: {mode}{c(RESET)}")
    lines.append("checking what the agent claimed against what the trace shows:")
    lines.append("")

    for r in receipts:
        mark, cname = _MARKS[r.verdict]
        lines.append(f'  {c(_COLORS[cname])}{mark} {r.verdict}{c(RESET)}  "{r.claim}"')
        lines.append(f"    {c(DIM)}{r.basis}{c(RESET)}")
        if r.evidence:
            for ev in r.evidence.splitlines()[:4]:
                lines.append(f"    {c(DIM)}| {ev}{c(RESET)}")
        lines.append("")

    counts = {v: sum(1 for r in receipts if r.verdict == v) for v in ("SUPPORTED", "CONTRADICTED", "UNVERIFIED")}
    lines.append("─" * 54)
    lines.append(f"{len(receipts)} claims · {counts['SUPPORTED']} supported · "
                 f"{counts['CONTRADICTED']} contradicted · {counts['UNVERIFIED']} unverified")
    return "\n".join(lines)
