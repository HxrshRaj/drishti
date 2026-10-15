"""Agent middleware. Each middleware can wrap tool calls or rewrite the message list
before a model call. Order matters: the first in the list is the outermost wrapper."""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .types import Message, ToolCall, ToolSpec

ToolRunner = Callable[[ToolCall], Any]


class ApprovalRequired(Exception):
    """Raised to pause a run until a human approves or rejects a tool call."""

    def __init__(self, call: ToolCall) -> None:
        super().__init__(f"approval required for {call.name}")
        self.call = call


class ToolError(Exception):
    """A tool failure that is safe to show the model (no secrets, no stack trace)."""


class Middleware:
    def before_model(self, messages: list[Message]) -> list[Message]:
        return messages

    def wrap_tool_call(self, call: ToolCall, spec: ToolSpec, nxt: ToolRunner) -> Any:
        return nxt(call)


@dataclass
class ToolRetry(Middleware):
    """Retry transient failures with exponential backoff. Validation errors and
    ToolError are not retried: repeating them cannot help."""

    max_attempts: int = 3
    base_delay: float = 0.0
    sleep: Callable[[float], None] = time.sleep
    retry_on: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError)

    def wrap_tool_call(self, call, spec, nxt):
        for attempt in range(1, self.max_attempts + 1):
            try:
                return nxt(call)
            except self.retry_on:
                if attempt == self.max_attempts:
                    raise
                self.sleep(self.base_delay * (2 ** (attempt - 1)))


class ErrorToMessage(Middleware):
    """Turn tool failures into a short result the model can react to, instead of
    crashing the run. Approval pauses are re-raised untouched."""

    def wrap_tool_call(self, call, spec, nxt):
        try:
            return nxt(call)
        except ApprovalRequired:
            raise
        except ToolError as e:
            return {"error": str(e)}
        except Exception as e:  # noqa: BLE001 - boundary: never leak a traceback to the model
            return {"error": f"{type(e).__name__}: tool failed"}


@dataclass
class ApprovalGate(Middleware):
    """Human-in-the-loop: tools marked requires_approval pause the run unless this
    exact call id was already approved. Rejected calls return a refusal result."""

    approved: set[str]
    rejected: set[str]

    def wrap_tool_call(self, call, spec, nxt):
        if not spec.requires_approval:
            return nxt(call)
        if call.id in self.rejected:
            return {"error": "rejected by human reviewer"}
        if call.id not in self.approved:
            raise ApprovalRequired(call)
        return nxt(call)


@dataclass
class ContextTrim(Middleware):
    """Keep the system prompt, the first user message and the most recent messages,
    dropping the middle once the estimated size passes a budget. Tool-call/tool-result
    pairs are never split."""

    max_chars: int = 6000

    def before_model(self, messages):
        if sum(len(m.content) for m in messages) <= self.max_chars:
            return messages
        head = [m for m in messages[:2]]
        tail: list[Message] = []
        size = sum(len(m.content) for m in head)
        for m in reversed(messages[2:]):
            size += len(m.content)
            if size > self.max_chars:
                break
            tail.append(m)
        tail.reverse()
        while tail and tail[0].role == "tool":  # don't start with an orphaned tool result
            tail.pop(0)
        dropped = len(messages) - len(head) - len(tail)
        note = Message("system", f"[{dropped} earlier messages trimmed to fit the context budget]")
        return head + [note] + tail


def compose(middlewares: list[Middleware], spec: ToolSpec, base: ToolRunner) -> ToolRunner:
    runner = base
    for mw in reversed(middlewares):
        runner = (lambda m, nxt: lambda call: m.wrap_tool_call(call, spec, nxt))(mw, runner)
    return runner
