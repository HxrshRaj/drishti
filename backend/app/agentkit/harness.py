"""The agent execution loop (harness): model call -> tool calls -> results -> repeat.

It owns the pieces an agent framework would otherwise hide: argument validation,
permission checks, a middleware chain around every tool call, per-call tracing,
token accounting, a step cap, and checkpointing so a run can pause for human
approval and resume later (even in another process).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from .checkpoint import CheckpointStore, SqliteCheckpointStore
from .middleware import ApprovalGate, ApprovalRequired, Middleware, ToolError, compose
from .tracing import get_tracer
from .types import ChatModel, Message, ToolCall, ToolSpec, Usage


@dataclass
class RunResult:
    run_id: str
    status: str  # completed | awaiting_approval | max_steps
    answer: str = ""
    steps: int = 0
    usage: Usage = field(default_factory=Usage)
    pending_call: ToolCall | None = None
    tool_trace: list[dict[str, Any]] = field(default_factory=list)


class AgentHarness:
    def __init__(
        self,
        model: ChatModel,
        tools: list[ToolSpec],
        middlewares: list[Middleware] | None = None,
        store: CheckpointStore | None = None,
        max_steps: int = 8,
        granted_permissions: set[str] | None = None,
        system_prompt: str = "You are a careful assistant. Use tools when needed.",
    ) -> None:
        self.model = model
        self.tools = {t.name: t for t in tools}
        self.store = store or SqliteCheckpointStore()
        self.max_steps = max_steps
        self.granted = granted_permissions if granted_permissions is not None else {"read"}
        self.system_prompt = system_prompt
        self._approved: set[str] = set()
        self._rejected: set[str] = set()
        self.middlewares = list(middlewares or [])
        if not any(isinstance(m, ApprovalGate) for m in self.middlewares):
            self.middlewares.insert(0, ApprovalGate(self._approved, self._rejected))

    # -- public API --------------------------------------------------------
    def run(self, task: str, run_id: str | None = None) -> RunResult:
        run_id = run_id or uuid.uuid4().hex[:12]
        state = {
            "messages": [Message("system", self.system_prompt).to_dict(), Message("user", task).to_dict()],
            "pending": [], "steps": 0, "usage": [0, 0], "trace": [],
        }
        return self._loop(run_id, state)

    def resume(self, run_id: str, approve: dict[str, bool] | None = None) -> RunResult:
        state = self.store.load(run_id)
        if state is None:
            raise KeyError(f"no checkpoint for run {run_id}")
        for call_id, ok in (approve or {}).items():
            (self._approved if ok else self._rejected).add(call_id)
        return self._loop(run_id, state)

    # -- internals ---------------------------------------------------------
    def _loop(self, run_id: str, state: dict[str, Any]) -> RunResult:
        tracer = get_tracer()
        usage = Usage(*state["usage"])
        with tracer.start_as_current_span("agent.run") as run_span:
            run_span.set_attribute("agent.run_id", run_id)
            while True:
                if state["pending"]:
                    paused = self._run_pending(state, run_id)
                    if paused:
                        return self._result(run_id, state, usage, "awaiting_approval", paused)
                    continue
                if state["steps"] >= self.max_steps:
                    run_span.set_attribute("agent.status", "max_steps")
                    return self._result(run_id, state, usage, "max_steps")
                messages = [Message.from_dict(m) for m in state["messages"]]
                for mw in self.middlewares:
                    messages = mw.before_model(messages)
                with tracer.start_as_current_span("agent.model_call") as s:
                    resp = self.model.generate(messages, list(self.tools.values()))
                    s.set_attribute("llm.model", getattr(self.model, "name", "unknown"))
                    s.set_attribute("llm.input_tokens", resp.usage.input_tokens)
                    s.set_attribute("llm.output_tokens", resp.usage.output_tokens)
                    s.set_attribute("llm.tool_calls", len(resp.tool_calls))
                usage.add(resp.usage)
                state["usage"] = [usage.input_tokens, usage.output_tokens]
                state["steps"] += 1
                state["messages"].append(Message("assistant", resp.text, resp.tool_calls).to_dict())
                if not resp.tool_calls:
                    run_span.set_attribute("agent.status", "completed")
                    self.store.save(run_id, {**state, "status": "completed"})
                    return self._result(run_id, state, usage, "completed", answer=resp.text)
                state["pending"] = [{"id": c.id, "name": c.name, "args": c.args} for c in resp.tool_calls]
                self.store.save(run_id, {**state, "status": "running"})

    def _run_pending(self, state: dict[str, Any], run_id: str) -> ToolCall | None:
        while state["pending"]:
            call = ToolCall(**state["pending"][0])
            try:
                result = self._execute(call)
            except ApprovalRequired as pause:
                self.store.save(run_id, {**state, "status": "awaiting_approval"})
                return pause.call
            state["pending"].pop(0)
            state["trace"].append({"tool": call.name, "args": call.args, "result": result,
                                   "error": "error" in result if isinstance(result, dict) else False})
            state["messages"].append(Message("tool", json.dumps(result, default=str), tool_call_id=call.id).to_dict())
            self.store.save(run_id, {**state, "status": "running"})
        return None

    def _execute(self, call: ToolCall) -> Any:
        tracer = get_tracer()
        with tracer.start_as_current_span("agent.tool_call") as span:
            span.set_attribute("tool.name", call.name)
            spec = self.tools.get(call.name)
            if spec is None:
                span.set_attribute("tool.error", "unknown_tool")
                return {"error": f"unknown tool '{call.name}'"}
            if spec.permission not in self.granted:
                span.set_attribute("tool.error", "permission_denied")
                return {"error": f"permission '{spec.permission}' not granted for {call.name}"}
            try:
                args = spec.args_model(**call.args)
            except ValidationError as e:
                span.set_attribute("tool.error", "invalid_arguments")
                return {"error": "invalid arguments: " + "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())}

            def base(c: ToolCall) -> Any:
                return spec.fn(**args.model_dump())

            runner = compose(self.middlewares, spec, base)
            try:
                result = runner(call)
            except ApprovalRequired:
                span.set_attribute("tool.awaiting_approval", True)
                raise
            except (ToolError, Exception) as e:  # noqa: BLE001
                span.set_attribute("tool.error", type(e).__name__)
                return {"error": f"{type(e).__name__}: tool failed"}
            if isinstance(result, dict) and "error" in result:
                span.set_attribute("tool.error", "tool_returned_error")
            return result

    def _result(self, run_id, state, usage, status, pending=None, answer="") -> RunResult:
        return RunResult(run_id, status, answer, state["steps"], usage, pending, list(state["trace"]))
