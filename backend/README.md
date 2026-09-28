# Drishti Backend

FastAPI service: VLM perception, LangGraph mission orchestration, the
AutoGen Perception-vs-Verifier exchange, the CrewAI reporting crew, RAG
over the SOP corpus, persistent memory, the safety/approval-gate layer,
and observability. See [`../docs/architecture.md`](../docs/architecture.md)
for how these fit together.

## Run locally (no Docker)

```bash
python -m venv .venv
# Windows
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
# macOS/Linux
# .venv/bin/pip install -r requirements-dev.txt
# .venv/bin/pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu

# ingest the SOP corpus into the vector store (Milvus Lite by default)
.venv\Scripts\python.exe -m app.rag.ingest

# make sure drone-gateway is running first (see ../drone-gateway/README.md)
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

API docs: http://localhost:8000/docs

## Tests

```bash
pytest -q
```

`tests/conftest.py::live_gateway_url` launches the real drone-gateway
service as a subprocess for orchestration/integration tests — real HTTP
calls into real gateway logic, not mocks. `tests/conftest.py::isolated_memory_db`
gives every test its own throwaway SQLite + Milvus Lite file (Milvus Lite
locks its file for exclusive per-process access, so tests never touch
`../data/milvus_lite.db`, which a locally running dev server or another
test run might have open).

## Layout

- `app/perception/` — the two-stage VLM pipeline (see `docs/architecture.md`
  for why it's two stages).
- `app/llm/` — the local Qwen2.5-0.5B model + the OpenAI-compatible gateway
  every agent framework points at by default.
- `app/agents/` — the AutoGen verifier exchange and the CrewAI reporting
  crew.
- `app/orchestration/` — the LangGraph mission workflow, the drone-gateway
  HTTP client, and the FastAPI routes that drive missions.
- `app/vectorstore/`, `app/rag/` — the `VectorStore` interface (Milvus
  Lite/standalone, Pinecone) and SOP chunking/ingestion/retrieval.
- `app/memory/`, `app/db/` — SQLAlchemy models and the repository layer for
  missions, findings, approvals, and the audit log.
- `app/safety/` — risk policy and the approval gate.
- `app/observability/` — structured JSON logging and LangSmith config.
