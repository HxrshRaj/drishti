import json

import httpx
from pydantic import BaseModel

from app.agentkit.llm_openai import OpenAICompatModel
from app.agentkit.types import Message, ToolSpec


class Args(BaseModel):
    order_id: str


TOOL = ToolSpec("lookup_order", "find an order", Args, lambda order_id: {})
REPLY = {"choices": [{"message": {"content": None, "tool_calls": [
    {"id": "t1", "type": "function", "function": {"name": "lookup_order", "arguments": '{"order_id": "A1"}'}}]}}],
    "usage": {"prompt_tokens": 42, "completion_tokens": 7}}


def _client(captured):
    def handler(req: httpx.Request) -> httpx.Response:
        captured["req"] = req
        captured["body"] = json.loads(req.content)
        return httpx.Response(200, json=REPLY)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_azure_request_shape_and_parsing():
    cap = {}
    m = OpenAICompatModel.azure("https://my-res.openai.azure.com/", "gpt4o-mini", "KEY", client=_client(cap))
    r = m.generate([Message("user", "where is A1?")], [TOOL])
    req = cap["req"]
    assert req.url.path == "/openai/deployments/gpt4o-mini/chat/completions"
    assert req.url.params["api-version"] == "2024-10-21"
    assert req.headers["api-key"] == "KEY" and "authorization" not in req.headers
    assert "model" not in cap["body"]  # Azure takes the deployment from the URL
    assert cap["body"]["tools"][0]["function"]["parameters"]["required"] == ["order_id"]
    assert r.tool_calls[0].args == {"order_id": "A1"} and (r.usage.input_tokens, r.usage.output_tokens) == (42, 7)


def test_openai_compat_uses_bearer_and_model_in_body():
    cap = {}
    m = OpenAICompatModel("gpt-4o-mini", "https://api.openai.com/v1", "SK", client=_client(cap))
    m.generate([Message("user", "hi")], [TOOL])
    assert cap["req"].headers["authorization"] == "Bearer SK" and cap["body"]["model"] == "gpt-4o-mini"


def test_unparseable_tool_arguments_become_a_validation_failure_not_a_crash():
    bad = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "t", "function": {"name": "lookup_order", "arguments": "{oops"}}]}}]}
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=bad)))
    r = OpenAICompatModel("m", "http://x", "k", client=c).generate([Message("user", "q")], [TOOL])
    assert "__unparseable__" in r.tool_calls[0].args
