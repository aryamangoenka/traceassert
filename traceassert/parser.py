# claude code session jsonl -> our IR. schema verified against a real
# session on this machine (2026-09-20): tool calls are tool_use blocks inside
# assistant messages, results arrive later in user messages as tool_result
# blocks keyed by tool_use_id, with is_error. the pairing below is the whole
# job: a call and its result must end up on the same event.

from __future__ import annotations

import json
from pathlib import Path

from .models import AssistantMessage, CommandRun, FileEdit, ToolCall, Trace, UserMessage

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}

# claude code writes its own bookkeeping into user turns. some carry isMeta,
# but /command records don't (verified on a real session, cli 2.1.221), so we
# also skip by their tag prefixes. these are never things the human typed.
SYNTHETIC_PREFIXES = ("<command-name>", "<local-command-stdout>", "<local-command-caveat>")


def _blocks(message: dict) -> list:
    # content is a plain string when a human typed it, else a list of blocks
    content = message.get("content", [])
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return content if isinstance(content, list) else []


def _flatten(content) -> str:
    # tool_result content is a string or a list of text blocks, either way
    # we want one string of raw output
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)


def _event_for_tool_use(eid: int, block: dict):
    name = block.get("name", "")
    inp = block.get("input", {}) or {}
    if name in EDIT_TOOLS:
        path = inp.get("file_path") or inp.get("notebook_path") or "?"
        return FileEdit(id=eid, path=path, tool=name, detail=inp)
    if name == "Bash":
        return CommandRun(id=eid, command=inp.get("command", ""))
    return ToolCall(id=eid, tool=name, input=inp)


def parse_trace(path: str | Path) -> Trace:
    trace = Trace(path=str(path))
    pending: dict[str, object] = {}  # tool_use_id -> the event waiting for its result

    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue  # real sessions have the odd non-json line, skip it

        kind = raw.get("type")
        if kind not in ("assistant", "user"):
            continue  # snapshots, attachments, queue ops... bookkeeping, not conduct
        if raw.get("isMeta"):
            # caveats, /command records, local command output. claude code
            # marks these itself, and they are NOT things the human said.
            # found via dogfooding: they were polluting user_request and the
            # authorization evidence.
            continue

        for block in _blocks(raw.get("message", {})):
            btype = block.get("type")

            if kind == "assistant" and btype == "tool_use":
                event = _event_for_tool_use(len(trace.events), block)
                trace.events.append(event)
                pending[block.get("id", "")] = event

            elif kind == "assistant" and btype == "text" and block.get("text", "").strip():
                trace.events.append(AssistantMessage(id=len(trace.events), text=block["text"]))

            elif kind == "user" and btype == "tool_result":
                event = pending.pop(block.get("tool_use_id", ""), None)
                if event is None:
                    continue  # result without a call we saw, tolerate it
                failed = bool(block.get("is_error", False))
                output = _flatten(block.get("content", ""))
                if isinstance(event, FileEdit):
                    event.applied = not failed
                elif isinstance(event, (CommandRun, ToolCall)):
                    event.output = output
                    event.failed = failed

            elif kind == "user" and btype == "text" and block.get("text", "").strip():
                if block["text"].lstrip().startswith(SYNTHETIC_PREFIXES):
                    continue
                trace.events.append(UserMessage(id=len(trace.events), text=block["text"]))

    return trace


def find_traces(path: str | Path) -> list[Path]:
    # a single .jsonl or a folder of them
    p = Path(path)
    if p.is_file():
        return [p]
    return sorted(p.glob("**/*.jsonl")) if p.is_dir() else []
