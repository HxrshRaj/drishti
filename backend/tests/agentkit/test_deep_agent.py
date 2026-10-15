from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.types import Command

from app.agentkit.deep_agent import build_deep_agent


class ScriptedChatModel(BaseChatModel):
    """Test double: replays AIMessages (with tool calls) in order."""

    script: list[Any]
    i: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kw):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kw):
        msg = self.script[min(self.i, len(self.script) - 1)]
        self.i += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


def ai(text="", **call):
    calls = [{"name": n, "args": a, "id": f"id_{n}"} for n, a in call.items()]
    return AIMessage(content=text, tool_calls=calls)


def test_deep_agent_runs_a_tool_and_emits_spans(spans):
    sink: list = []
    model = ScriptedChatModel(script=[ai(get_invoice={"invoice_id": "INV-1001"}), ai("Invoice INV-1001 is paid.")])
    agent = build_deep_agent(model, sink)
    out = agent.invoke({"messages": [HumanMessage("status of INV-1001?")]}, {"configurable": {"thread_id": "t1"}})
    tool_msgs = [m for m in out["messages"] if isinstance(m, ToolMessage) and m.name == "get_invoice"]
    assert tool_msgs and "paid" in tool_msgs[0].content
    assert "paid" in out["messages"][-1].content
    names = [(s.name, (s.attributes or {}).get("tool.name")) for s in spans.get_finished_spans()]
    assert ("agent.tool_call", "get_invoice") in names


def test_refund_interrupts_and_only_executes_after_approval(spans):
    sink: list = []
    model = ScriptedChatModel(script=[ai(issue_refund={"invoice_id": "INV-1001", "amount": 100.0}), ai("Refunded 100.")])
    agent = build_deep_agent(model, sink)
    cfg = {"configurable": {"thread_id": "t2"}}
    paused = agent.invoke({"messages": [HumanMessage("refund 100 on INV-1001")]}, cfg)
    assert "__interrupt__" in paused and sink == []  # nothing executed yet
    agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg)
    assert sink == [("refund", "INV-1001", 100.0)]


def test_rejected_refund_never_runs(spans):
    sink: list = []
    model = ScriptedChatModel(script=[ai(issue_refund={"invoice_id": "INV-1001", "amount": 100.0}), ai("Understood, no refund.")])
    agent = build_deep_agent(model, sink)
    cfg = {"configurable": {"thread_id": "t3"}}
    agent.invoke({"messages": [HumanMessage("refund 100 on INV-1001")]}, cfg)
    agent.invoke(Command(resume={"decisions": [{"type": "reject", "message": "not allowed"}]}), cfg)
    assert sink == []
