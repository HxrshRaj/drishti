"""The same support toolset as a DeepAgents agent (LangGraph under the hood): planning
todos, a virtual filesystem, sub-agents, human-in-the-loop interrupts on risky tools,
a checkpointer for pause/resume, and custom middleware that traces every tool call."""
from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver

from .evals.toolset import build_tools
from .tracing import get_tracer


class TracingMiddleware(AgentMiddleware):
    """Wraps every tool call in an OpenTelemetry span, same attributes as the harness."""

    def wrap_tool_call(self, request, handler):
        name = request.tool_call["name"]
        with get_tracer().start_as_current_span("agent.tool_call") as span:
            span.set_attribute("tool.name", name)
            result = handler(request)
            if getattr(result, "status", None) == "error":
                span.set_attribute("tool.error", "tool_error")
            return result


def as_langchain_tools(sink: list | None = None) -> list[StructuredTool]:
    return [StructuredTool.from_function(func=t.fn, name=t.name, description=t.description, args_schema=t.args_model)
            for t in build_tools(sink)]


def build_deep_agent(model: Any, sink: list | None = None, checkpointer: Any = None):
    return create_deep_agent(
        model=model,
        tools=as_langchain_tools(sink),
        system_prompt="You are a support operations agent. Plan with todos, use tools, and never refund without approval.",
        middleware=[TracingMiddleware()],
        interrupt_on={"issue_refund": True},  # human approves, edits or rejects refunds
        checkpointer=checkpointer or MemorySaver(),
        name="support-deep-agent",
    )
