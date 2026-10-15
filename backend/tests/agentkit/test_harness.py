import pytest
from pydantic import BaseModel

from app.agentkit.checkpoint import MongoCheckpointStore, SqliteCheckpointStore
from app.agentkit.harness import AgentHarness
from app.agentkit.middleware import ContextTrim, ErrorToMessage, ToolRetry
from app.agentkit.tracing import summarize_spans
from app.agentkit.types import Message, ToolSpec

from .fakes import ScriptedModel, call, resp


class AddArgs(BaseModel):
    a: int
    b: int


class NoteArgs(BaseModel):
    text: str


def make_tools(calls_log, flaky_failures=0):
    state = {"n": 0}

    def add(a, b):
        state["n"] += 1
        if state["n"] <= flaky_failures:
            raise TimeoutError("upstream timeout")
        return {"sum": a + b}

    def write_note(text):
        calls_log.append(text)
        return {"saved": True}

    return [
        ToolSpec("add", "add numbers", AddArgs, add),
        ToolSpec("write_note", "save a note", NoteArgs, write_note, requires_approval=True, permission="write"),
    ], state


def test_tool_call_loop_completes_and_counts_tokens(spans):
    tools, _ = make_tools([])
    model = ScriptedModel([resp("", call("c1", "add", a=2, b=3)), resp("the sum is 5")])
    r = AgentHarness(model, tools).run("add 2 and 3")
    assert r.status == "completed" and r.answer == "the sum is 5"
    assert (r.usage.input_tokens, r.usage.output_tokens) == (20, 10)
    s = summarize_spans(spans.get_finished_spans())
    assert s["model_calls"] == 2 and s["tool_calls"] == 1 and s["input_tokens"] == 20


def test_invalid_arguments_are_returned_to_the_model_not_executed(spans):
    tools, state = make_tools([])
    model = ScriptedModel([resp("", call("c1", "add", a="x")), resp("sorry")])
    r = AgentHarness(model, tools).run("go")
    assert state["n"] == 0  # function never ran
    assert "invalid arguments" in model.seen[1][-1].content
    assert r.tool_trace[0]["error"] is True


def test_unknown_tool_and_missing_permission(spans):
    tools, _ = make_tools([])
    model = ScriptedModel([resp("", call("c1", "nope"), call("c2", "write_note", text="x")), resp("done")])
    r = AgentHarness(model, tools, granted_permissions={"read"}).run("go")
    contents = [m.content for m in model.seen[1] if m.role == "tool"]
    assert "unknown tool" in contents[0] and "permission 'write' not granted" in contents[1]
    assert r.status == "completed"


def test_retry_recovers_from_transient_failure_and_is_traced(spans):
    tools, state = make_tools([], flaky_failures=2)
    model = ScriptedModel([resp("", call("c1", "add", a=1, b=1)), resp("2")])
    r = AgentHarness(model, tools, [ErrorToMessage(), ToolRetry(max_attempts=3)]).run("go")
    assert state["n"] == 3 and r.status == "completed"
    assert r.tool_trace[0]["error"] is False


def test_retry_gives_up_and_error_reaches_model(spans):
    tools, state = make_tools([], flaky_failures=99)
    model = ScriptedModel([resp("", call("c1", "add", a=1, b=1)), resp("failed")])
    AgentHarness(model, tools, [ErrorToMessage(), ToolRetry(max_attempts=2)]).run("go")
    assert state["n"] == 2
    assert "tool failed" in model.seen[1][-1].content
    assert "upstream timeout" not in model.seen[1][-1].content  # no raw error leaked


def test_approval_pauses_then_resumes_from_checkpoint_in_a_new_harness(spans, tmp_path):
    log = []
    tools, _ = make_tools(log)
    store = SqliteCheckpointStore(str(tmp_path / "cp.db"))
    h1 = AgentHarness(ScriptedModel([resp("", call("w1", "write_note", text="hi"))]), tools,
                      granted_permissions={"read", "write"}, store=store)
    r1 = h1.run("save a note", run_id="run-1")
    assert r1.status == "awaiting_approval" and r1.pending_call.id == "w1" and log == []
    # A brand-new harness (a different process in real life) resumes from the checkpoint.
    h2 = AgentHarness(ScriptedModel([resp("saved it")]), tools, granted_permissions={"read", "write"}, store=store)
    r2 = h2.resume("run-1", approve={"w1": True})
    assert r2.status == "completed" and log == ["hi"]


def test_rejected_call_is_not_executed(spans):
    log = []
    tools, _ = make_tools(log)
    h = AgentHarness(ScriptedModel([resp("", call("w1", "write_note", text="x"))]), tools,
                     granted_permissions={"read", "write"})
    assert h.run("go", run_id="r").status == "awaiting_approval"
    h.model = ScriptedModel([resp("ok, not saved")])
    r = h.resume("r", approve={"w1": False})
    assert r.status == "completed" and log == []


def test_step_cap_stops_a_looping_agent(spans):
    tools, _ = make_tools([])
    model = ScriptedModel([resp("", call(f"c{i}", "add", a=1, b=1)) for i in range(10)])
    r = AgentHarness(model, tools, max_steps=3).run("loop")
    assert r.status == "max_steps" and r.steps == 3


def test_context_trim_keeps_head_and_recent_and_never_orphans_tool_result():
    msgs = [Message("system", "s"), Message("user", "u")] + [Message("assistant", "x" * 100) for _ in range(30)]
    msgs.insert(20, Message("tool", "r" * 100, tool_call_id="c"))
    out = ContextTrim(max_chars=1000).before_model(msgs)
    assert out[0].content == "s" and out[1].content == "u" and "trimmed" in out[2].content
    assert len(out) < len(msgs) and out[3].role != "tool"


@pytest.fixture
def mongo_collection():
    import mongomock

    return mongomock.MongoClient()["agentkit"]["checkpoints"]


def test_mongo_store_round_trip(mongo_collection):
    store = MongoCheckpointStore(mongo_collection)
    store.save("r1", {"steps": 2, "messages": [{"role": "user", "content": "hi"}]})
    store.save("r1", {"steps": 3, "messages": []})  # upsert
    assert store.load("r1")["steps"] == 3 and store.load("missing") is None


def test_pause_resume_works_on_the_mongo_store(spans, mongo_collection):
    log = []
    tools, _ = make_tools(log)
    store = MongoCheckpointStore(mongo_collection)
    h = AgentHarness(ScriptedModel([resp("", call("w1", "write_note", text="m"))]), tools,
                     granted_permissions={"read", "write"}, store=store)
    h.run("go", run_id="m1")
    h2 = AgentHarness(ScriptedModel([resp("done")]), tools, granted_permissions={"read", "write"}, store=store)
    assert h2.resume("m1", approve={"w1": True}).status == "completed" and log == ["m"]
