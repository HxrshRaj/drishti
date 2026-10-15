"""Chat-completions adapter with tool calling for OpenAI, Azure OpenAI and any
OpenAI-compatible server (Ollama, vLLM, this repo's local gateway)."""
from __future__ import annotations

import json

import httpx

from .types import Message, ModelResponse, ToolCall, ToolSpec, Usage


class OpenAICompatModel:
    def __init__(self, model: str, base_url: str, api_key: str, *, azure_api_version: str | None = None,
                 client: httpx.Client | None = None, timeout: float = 60.0) -> None:
        self.name = model
        self.api_key = api_key
        self.azure_api_version = azure_api_version
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout)

    @classmethod
    def azure(cls, endpoint: str, deployment: str, api_key: str, api_version: str = "2024-10-21", **kw) -> OpenAICompatModel:
        """Azure OpenAI: the deployment name is in the URL, the key goes in `api-key`,
        and every call carries an api-version query parameter."""
        base = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
        return cls(deployment, base, api_key, azure_api_version=api_version, **kw)

    def _request_parts(self) -> tuple[str, dict[str, str], dict[str, str]]:
        url = f"{self.base_url}/chat/completions"
        if self.azure_api_version:
            return url, {"api-key": self.api_key}, {"api-version": self.azure_api_version}
        return url, {"Authorization": f"Bearer {self.api_key}"}, {}

    @staticmethod
    def _wire_messages(messages: list[Message]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            d: dict = {"role": m.role, "content": m.content}
            if m.tool_calls:
                d["tool_calls"] = [{"id": c.id, "type": "function",
                                    "function": {"name": c.name, "arguments": json.dumps(c.args)}} for c in m.tool_calls]
            if m.tool_call_id:
                d["tool_call_id"] = m.tool_call_id
            out.append(d)
        return out

    def generate(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        url, headers, params = self._request_parts()
        body: dict = {"messages": self._wire_messages(messages)}
        if not self.azure_api_version:
            body["model"] = self.name
        if tools:
            body["tools"] = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.args_model.model_json_schema()}}
                for t in tools]
        r = self.client.post(url, json=body, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        msg = data["choices"][0]["message"]
        calls = []
        for c in msg.get("tool_calls") or []:
            try:
                args = json.loads(c["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {"__unparseable__": c["function"]["arguments"]}  # fails validation; the model sees why
            calls.append(ToolCall(c["id"], c["function"]["name"], args))
        u = data.get("usage") or {}
        return ModelResponse(msg.get("content") or "", calls, Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0)))
