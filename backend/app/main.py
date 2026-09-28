from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.llm.openai_compat_router import router as llm_router
from app.observability.langsmith import configure_langsmith
from app.observability.metrics_router import router as metrics_router
from app.orchestration.router import router as mission_router
from app.perception.router import router as perception_router

app = FastAPI(
    title="Drishti Backend",
    description="Perception, orchestration, agents, RAG/memory, and safety layer for the Drishti aerial inspection demo. The drone fleet is simulated — see drone-gateway/.",
    version="0.1.0",
)

_langsmith_enabled = configure_langsmith()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(perception_router)
app.include_router(llm_router)
app.include_router(mission_router)
app.include_router(metrics_router)


@app.get("/health")
def health():
    return {"status": "ok", "langsmith_tracing": _langsmith_enabled}
