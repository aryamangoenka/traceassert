# the contract (v1)

what traceassert is and is not. v0 of this file described five semantic rules judged by jev, kept as the appendix below and still runnable as `traceassert test`. the claim checker replaced it as the product after the experiment and the eval numbers in the readme. changes to this file get logged in the decision log, not argued about forever.

## what goes in

one claude code session trace (the .jsonl files claude keeps under `~/.claude/projects/`). other agents come later via adapters, the core never learns their formats.

## what comes out

one receipt per claim the agent made in its final message, plus a report in the terminal. exit code 1 if any claim is CONTRADICTED, so it drops straight into ci.

a receipt looks like:

```
claim        the agent's sentence, verbatim
verdict      SUPPORTED, CONTRADICTED, or UNVERIFIED
basis        how we decided, in plain words, always prefixed "deterministic:" or "routed:"
evidence     the raw receipt: the test output, the file paths, the command
event_ids    which trace events this came from, so you can go look yourself
```

## the three verdicts, and what each one means

- **SUPPORTED**: the trace shows evidence that backs the claim. for a deterministic check that's proof (the run with 12 passed exists). for a routed check it means related evidence exists, and the basis says so in those words.
- **CONTRADICTED**: the trace shows something that conflicts with the claim. this needs POSITIVE contradicting evidence. absence of evidence is never a contradiction when the absence could be a detection gap (agents write files through shell heredocs, and we can't always read the target).
- **UNVERIFIED**: we couldn't find evidence either way. an honest gap, not an accusation. this is the whole reason there is no FAIL.

## the pipeline

```
jsonl -> parser -> IR (facts) -> extraction (claims, modifications) -> classify (code) -> check per type -> receipts -> report
```

- the IR holds facts only: UserMessage, AssistantMessage, FileEdit, CommandRun, ToolCall.
- extraction derives interpretations from facts: Claim sentences (with the sentence before each, for pronouns), and Modifications (a FileEdit OR a write-ish shell command, scanned heredoc-aware, with the target marked unclear when it can't be read off the command).
- classification is regex, deliberately: auditable and boring. five types plus other.
- each type has its own check, and the cheapest reliable method wins.

## the big rules of this codebase

1. **code narrows, jev routes, the evidence decides.** test counts, exit codes, path matches and file lists are decided by code. jev is asked exactly one kind of question: is this candidate edit or command relevant to this claim. jev is never asked whether a claim is true, never asked whether the agent was good, and never sees the whole trace.
2. **never accuse on absence.** a CONTRADICTED verdict needs something in the trace that conflicts. "no file edits" is not proof of "no changes" when shell writes with unreadable targets happened. those cases say so and stop at UNVERIFIED.
3. **accusing costs more than supporting.** contradicting a "didn't touch it" claim through the router needs relevance of .8 or better. between .5 and .8 the receipt says "might", not a verdict. when the claim names a path, none of this applies, it's fnmatch.
4. **every basis says how it was decided.** `deterministic:` or `routed:`. a routed relevance match is not a proof and the receipt never pretends it is.
5. **every number about this tool is measured and linked.** smoke evals live in `evals/`, results in `evals/results/`. thresholds (.5 relevance, .8 accusation) are admitted placeholders until calibration data exists.

## what leaves your machine

when jev gets asked, the claim sentence (plus the sentence before it) and a short summary of one candidate edit or command go to typesafe's cloud api. nothing else. without a key nothing leaves at all: the deterministic checks still run and routed claims say "routing not configured" instead of guessing. published traces in `experiment/runs/` were scrubbed with `experiment/redact.py`, which is in the repo so anyone can see exactly what was removed.

## known limits of v1 (found by running it on real sessions, kept honestly)

- claims come from the agent's FINAL message only. mid-session claims are a later item.
- claims about ci, prs, deploys, or anything not visible in a local trace have no check yet and show as unverified.
- the classifier is regex. known misses: "no changes to the api" (negation noun, no verb) and "it fails without the fix and passes with it" (no test word). both measured in `evals/results/2026-09-21-router.json`.
- compound sentences take their first matching type. claim extraction splits on sentences so this is rare.
- a shell write whose target can't be read off the command caps every verdict that depends on it at UNVERIFIED. we would rather say "can't tell" than guess.

## appendix: v0, the rule engine

`traceassert test <trace> [--prohibit GLOB]` still runs five semantic rules (scope, unsupported-claim, destructive-without-authorization, repeated-failed-action, final-summary-accuracy) with FAIL / REVIEW buckets at .90 / .60, judged by jev on single-hop questions. it is kept working while the claim checker proves out. on the 20 frozen experiment traces it produced 23 FAIL and 29 REVIEW findings, nearly all false positives from composite command output; the claim checker on the same traces produced 0 contradictions. that comparison is why the thesis changed.
