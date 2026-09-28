"""LangSmith tracing, enabled only when LANGSMITH_API_KEY is present (see
docs/limitations.md — this environment does not have one, so live tracing
is listed as pending, not asserted). LangGraph and LangChain auto-instrument
once these standard env vars are set — no per-node code changes needed.
"""
from __future__ import annotations

import os

from app.config import settings


def configure_langsmith() -> bool:
    if not settings.langsmith_api_key:
        return False
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    return True
