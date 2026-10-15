"""A deterministic rule-based stand-in for an LLM, so the eval pipeline, metrics and
regression gate can run in CI with no API key. It reads the task with regexes and
answers from tool results. It is NOT a measure of any real model: run the same
suite against a real model with `--model openai|azure` (see README)."""
from __future__ import annotations

import json
import re

from ..types import Message, ModelResponse, ToolCall, ToolSpec, Usage


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)  # rough estimate, labelled as such in reports


class ReferenceModel:
    name = "reference-rules"

    def generate(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        used = sum(_tokens(m.content) for m in messages)
        if not any(m.role == "tool" for m in messages):
            task = next(m.content for m in messages if m.role == "user")
            calls = self.plan(task)
            if calls:
                return ModelResponse("", calls, Usage(used, 20 * len(calls)))
        results = [m.content for m in messages if m.role == "tool"]
        text = " | ".join(self.render(r) for r in results) or "I could not find a tool for that."
        return ModelResponse(text, [], Usage(used, _tokens(text)))

    # overridable so degraded variants can be tested against the regression gate
    def plan(self, task: str) -> list[ToolCall]:
        low = task.lower()
        calls: list[ToolCall] = []
        n = 0

        def add(name: str, **args) -> None:
            nonlocal n
            n += 1
            calls.append(ToolCall(f"call_{n}", name, args))

        refund = re.search(r"refund (\d+(?:\.\d+)?) on invoice (INV-\d+)", task, re.I)
        for inv in dict.fromkeys(re.findall(r"INV-\d+", task)):
            if not task.lstrip().lower().startswith("refund"):
                add("get_invoice", invoice_id=inv)
        for email in re.findall(r"[\w.]+@[\w.]+\.\w+", task):
            add("find_customer", email=email)
        if "policy" in low:
            add("get_policy", topic="support" if "support" in low else "refund")
        title = re.search(r"ticket titled '([^']+)'", task)
        if title:
            pr = "high" if "high priority" in low else "low" if "low priority" in low else "normal"
            add("create_ticket", title=title.group(1), priority=pr)
        if refund and "policy" not in low:
            add("issue_refund", invoice_id=refund.group(2), amount=float(refund.group(1)))
        return calls

    @staticmethod
    def render(raw: str) -> str:
        d = json.loads(raw)
        return str(d["error"]) if "error" in d else ", ".join(f"{k} {v}" for k, v in d.items())
