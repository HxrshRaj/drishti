"""Core types for the agent harness: messages, tools, model responses."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class Message:
    role: str  # system | user | assistant | tool
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": [{"id": c.id, "name": c.name, "args": c.args} for c in self.tool_calls],
            "tool_call_id": self.tool_call_id,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Message:
        return Message(
            role=d["role"],
            content=d.get("content", ""),
            tool_calls=[ToolCall(**c) for c in d.get("tool_calls", [])],
            tool_call_id=d.get("tool_call_id"),
        )


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens


@dataclass
class ModelResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class ChatModel(Protocol):
    name: str

    def generate(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse: ...


@dataclass
class ToolSpec:
    """A tool the agent may call. `args_model` validates arguments before the
    function runs; `requires_approval` routes the call through the human-in-the-loop
    gate; `permission` is checked against the harness's granted permissions."""

    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[..., Any]
    requires_approval: bool = False
    permission: str = "read"
