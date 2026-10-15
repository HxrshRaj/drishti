"""Deterministic stand-in models for tests. These are labelled test doubles: they
script the model's behaviour so the HARNESS (validation, retries, approval, tracing,
checkpointing) can be tested exactly. They say nothing about real model quality."""
from __future__ import annotations

from app.agentkit.types import Message, ModelResponse, ToolCall, ToolSpec, Usage


class ScriptedModel:
    name = "scripted"

    def __init__(self, script: list[ModelResponse]) -> None:
        self.script = list(script)
        self.seen: list[list[Message]] = []

    def generate(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        self.seen.append(messages)
        return self.script.pop(0)


def call(i: str, name: str, **args) -> ToolCall:
    return ToolCall(i, name, args)


def resp(text: str = "", *calls: ToolCall, i: int = 10, o: int = 5) -> ModelResponse:
    return ModelResponse(text, list(calls), Usage(i, o))
