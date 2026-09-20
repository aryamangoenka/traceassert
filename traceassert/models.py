# the IR. facts only, on purpose (docs/contract.md). "this sentence is a
# claim" is an interpretation, so it is NOT an event here, claims get derived
# later in the extraction layer. every event keeps its id so findings can
# point back at exactly where in the session something happened.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UserMessage:
    id: int
    text: str


@dataclass
class AssistantMessage:
    id: int
    text: str


@dataclass
class FileEdit:
    id: int
    path: str
    tool: str  # Edit / Write / NotebookEdit
    detail: dict  # the raw tool input, old/new strings live here
    applied: bool = True  # flips False when the tool_result came back is_error


@dataclass
class CommandRun:
    id: int
    command: str
    output: str = ""
    failed: bool = False  # is_error on the tool_result, straight from the trace


@dataclass
class ToolCall:
    # everything that isn't an edit or a command (Read, Grep, web fetches...).
    # kept around so rules like "repeated failed action" see the whole picture.
    id: int
    tool: str
    input: dict
    output: str = ""
    failed: bool = False


@dataclass
class Trace:
    path: str
    events: list = field(default_factory=list)  # session order, ids match index

    @property
    def user_request(self) -> str:
        # the first thing the human asked for, scope judgments hang off this
        for e in self.events:
            if isinstance(e, UserMessage):
                return e.text
        return ""

    @property
    def final_message(self) -> str:
        # the last thing the agent said, the "done!" we fact-check
        for e in reversed(self.events):
            if isinstance(e, AssistantMessage):
                return e.text
        return ""

    @property
    def user_messages(self) -> list[UserMessage]:
        # everything the human said, authorization questions judge against this
        return [e for e in self.events if isinstance(e, UserMessage)]

    @property
    def file_edits(self) -> list[FileEdit]:
        return [e for e in self.events if isinstance(e, FileEdit)]

    @property
    def command_runs(self) -> list[CommandRun]:
        return [e for e in self.events if isinstance(e, CommandRun)]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.events:
            name = type(e).__name__
            out[name] = out.get(name, 0) + 1
        return out
