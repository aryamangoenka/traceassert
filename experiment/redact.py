# scrub machine-specific stuff out of the run artifacts before they go public.
# text-level substitutions on purpose: simple to read, simple to audit, and the
# whole point of publishing this script is that anyone can see exactly what was
# removed. nothing semantic is touched, only who ran it and where.
#
# the rules are derived from THIS machine at runtime (home dir, uid, git email)
# rather than hardcoded, because a redaction script with your username in it
# would leak the username.
#
#   uv run python experiment/redact.py            # ~/traceassert-runs/run-* -> experiment/runs/
#   uv run python experiment/redact.py --verify   # fail loudly if anything personal survived

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

SRC = Path.home() / "traceassert-runs"
DST = Path(__file__).parent / "runs"
FILES = ["trace.jsonl", "diff.patch", "agent-output.txt", "verdict.json", "check.txt"]


def _rules():
    home = str(Path.home())
    user = Path.home().name
    uid = str(os.getuid())
    email = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True).stdout.strip()
    rules = [
        (re.compile(re.escape(home)), "/Users/USER"),
        (re.compile(re.escape(home.replace("/", "-"))), "-Users-USER"),  # claude's encoded project dirs
        (re.compile(re.escape(user)), "USER"),
        (re.compile(rf"claude-{uid}\b"), "claude-UID"),  # scratchpad paths carry the uid
    ]
    if email:
        rules.append((re.compile(re.escape(email)), "USER@example.com"))
    # the account email in the traces is not the git email, found that out by
    # scanning, so every email-shaped string goes, not just the derived one
    rules.append((re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "USER@example.com"))
    # belt and braces: anything that looks like a key never ships, even though
    # the agents never had one
    rules.append((re.compile(r"(JEV_API_KEY|TYPESAFE_API_KEY)=\S+"), r"\1=REDACTED"))
    rules.append((re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "sk-REDACTED"))
    leak = re.compile("|".join([re.escape(user), r"@gmail\.com", rf"claude-{uid}\b",
                                r"(JEV_API_KEY|TYPESAFE_API_KEY)=(?!REDACTED)\S{4,}", r"\bsk-(?!REDACTED)[A-Za-z0-9_-]{16,}"]
                               + ([re.escape(email)] if email else [])), re.I)
    return rules, leak


def redact_text(text: str, rules) -> str:
    for rx, rep in rules:
        text = rx.sub(rep, text)
    return text


def publish() -> int:
    rules, _ = _rules()
    runs = sorted(p for p in SRC.glob("run-*") if p.is_dir())
    if not runs:
        sys.exit(f"no frozen runs under {SRC}")
    DST.mkdir(exist_ok=True)
    for run in runs:
        out = DST / run.name
        out.mkdir(exist_ok=True)
        for name in FILES:
            src = run / name
            if src.exists():
                (out / name).write_text(redact_text(src.read_text(errors="replace"), rules))
    # results.csv = the frozen rows only, pilots were disclosed and discarded
    lines = (SRC / "runs.csv").read_text().splitlines()
    kept = [lines[0]] + [l for l in lines[1:] if l.startswith("run-")]
    (DST.parent / "results.csv").write_text("\n".join(kept) + "\n")
    print(f"published {len(runs)} runs to {DST} and results.csv ({len(kept) - 1} rows)")
    return 0


def verify() -> int:
    _, leak = _rules()
    bad = []
    for path in list(DST.rglob("*")) + [DST.parent / "results.csv"]:
        if path.is_file():
            for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if leak.search(line):
                    bad.append(f"{path.relative_to(DST.parent)}:{i}")
    if bad:
        print("LEAK, personal strings survived redaction:")
        for b in bad[:20]:
            print("  ", b)
        return 1
    print(f"verified: nothing personal in {DST} or results.csv")
    return 0


if __name__ == "__main__":
    sys.exit(verify() if "--verify" in sys.argv else publish())
