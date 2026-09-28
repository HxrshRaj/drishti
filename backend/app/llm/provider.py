"""Resolves which LLM backend agent frameworks should use: a real hosted
provider if the user supplied a key (ANTHROPIC_API_KEY / OPENAI_API_KEY),
otherwise this project's own local OpenAI-compatible gateway
(app.llm.openai_compat_router) serving Qwen2.5-0.5B-Instruct — so the full
multi-agent system runs with zero credentials.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass
class LLMBackend:
    kind: str  # "local" | "anthropic" | "openai"
    model: str
    base_url: str | None = None
    api_key: str | None = None


def resolve_llm_backend(local_base_url: str = "http://localhost:8000/v1") -> LLMBackend:
    if settings.anthropic_api_key:
        return LLMBackend(kind="anthropic", model="claude-haiku-4-5-20251001", api_key=settings.anthropic_api_key)
    if settings.openai_api_key:
        return LLMBackend(kind="openai", model="gpt-4o-mini", api_key=settings.openai_api_key)
    return LLMBackend(kind="local", model="local-qwen2.5-0.5b", base_url=local_base_url, api_key="not-needed")
