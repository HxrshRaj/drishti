from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agentkit.tracing import traced_node


def test_traced_nodes_record_pause_as_attribute_not_error(spans):
    def gate(state):
        ok = interrupt("approve?")
        return {"approved": ok}

    def done(state):
        return {"done": True}

    g = StateGraph(dict)
    g.add_node("gate", traced_node("gate", gate))
    g.add_node("done", traced_node("done", done))
    g.add_edge(START, "gate")
    g.add_edge("gate", "done")
    g.add_edge("done", END)
    app = g.compile(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "x"}}
    app.invoke({}, cfg)
    app.invoke(Command(resume=True), cfg)
    node_spans = [s for s in spans.get_finished_spans() if s.name == "mission.node"]
    gates = [s for s in node_spans if s.attributes["mission.node"] == "gate"]
    assert any(s.attributes.get("mission.interrupted") for s in gates)
    assert not any("mission.error" in s.attributes for s in node_spans)
    assert any(s.attributes["mission.node"] == "done" for s in node_spans)
