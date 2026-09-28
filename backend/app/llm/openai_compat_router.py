"""Minimal OpenAI-compatible /v1/chat/completions endpoint backed by the
local Qwen2.5-0.5B-Instruct model. This lets every agent framework in this
project (LangChain's ChatOpenAI, AutoGen's OpenAIChatCompletionClient,
CrewAI's LLM) point at one real local inference endpoint via a plain
base_url override, instead of needing a bespoke client class per
framework — the same pattern used to point these frameworks at a
self-hosted vLLM/TGI server in production.
"""
from __future__ import annotations

import time
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.llm.local_llm import get_local_llm

router = APIRouter(prefix="/v1", tags=["llm-gateway"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "local-qwen2.5-0.5b"
    messages: list[ChatMessage]
    temperature: float = 0.2
    max_tokens: int = 300
    stream: bool = False


@router.post("/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    llm = get_local_llm()
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    text = llm.chat(messages, max_new_tokens=req.max_tokens, temperature=req.temperature)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": text},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@router.get("/models")
def list_models():
    llm = get_local_llm()
    return {"object": "list", "data": [{"id": llm.model_id, "object": "model"}]}
