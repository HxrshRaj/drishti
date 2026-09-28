# Drishti — Agentic Aerial Inspection Platform

Drishti is a full-stack demo of an agentic pipeline for aerial site
inspection: a vision-language model reads captured imagery, a
Perception-vs-Verifier agent exchange checks each other's work, a
LangGraph mission workflow orchestrates the flight plan with human-in-the-
loop approval gates, and a CrewAI crew turns accepted findings into a
report — all backed by a RAG layer over site SOPs and a persistent memory
of past findings.

**The drone fleet is entirely simulated.** No physical drone or robot is
controlled by this project, anywhere. See [`drone-gateway/`](drone-gateway)
— it is a FastAPI service that simulates fleet state and serves imagery
from a licensed aerial-imagery dataset in place of a live camera feed.

> Status: built incrementally, phase by phase, with each phase verified by
> a real run before moving on. See the bottom of this README for exactly
> what has been verified vs. simulated vs. still pending credentials.

## Why this exists

This project was built to demonstrate the specific capabilities named in a
job posting for an Agentic AI Engineer role at a drone-autonomy company:
multi-agent frameworks with agent-to-agent communication, RAG + persistent
memory, VLM perception for aerial imagery, agents that call real tools and
APIs, GPU-efficiency/latency measurement, LangSmith observability, and
human-in-the-loop safety (approval gates, fallback protocols, parity
checks).

## Architecture at a glance

```
                         ┌────────────────────────┐
   operator goal  ───▶   │   LangGraph mission     │
                         │   workflow (plan →      │
                         │   dispatch → perceive →  │
   SOPs (RAG) ────▶      │   verify → decide →      │  ◀── interrupt() for
   memory ─────────▶     │   report), checkpointed  │      human approval
                         └───────────┬─────────────┘
                                     │ tool calls (HTTP)
                    ┌────────────────┼─────────────────┐
                    ▼                ▼                 ▼
          ┌──────────────┐  ┌────────────────┐  ┌───────────────┐
          │ drone-gateway │  │ Perception VLM  │  │ AutoGen        │
          │ (simulated    │  │ (schema-JSON    │  │ Perception vs  │
          │  fleet, FastAPI)│ │  findings)      │  │ Verifier       │
          └──────────────┘  └────────────────┘  └───────┬───────┘
                                                          ▼
                                                 ┌────────────────┐
                                                 │ CrewAI Analyst  │
                                                 │ + Report Writer │
                                                 └────────────────┘
```

See [`docs/architecture.md`](docs/architecture.md) for the full breakdown
of why each framework owns which slice, and where the seams are awkward.

## Repository layout

- [`backend/`](backend) — FastAPI app: perception service, LangGraph
  orchestration, AutoGen verifier, CrewAI reporting crew, vector store /
  RAG, persistent memory, safety layer, observability.
- [`drone-gateway/`](drone-gateway) — simulated drone fleet, its own
  FastAPI service, with failure injection.
- [`frontend/`](frontend) — Next.js operator dashboard.
- [`benchmarks/`](benchmarks) — dataset sampling, latency/throughput/
  accuracy benchmarking, retrieval-quality eval.
- [`data/`](data) — sampled licensed imagery + labels, self-authored SOP
  corpus, memory store.
- [`docs/`](docs) — architecture, benchmarks, safety, bias report, data
  provenance, limitations.
- [`deploy/`](deploy) — GCP Cloud Run deployment scripts.

## Running it locally

```bash
cp .env.example .env   # fill in what you have; everything degrades gracefully without keys
docker compose up --build
```

- Backend API: http://localhost:8000
- Drone gateway (simulated): http://localhost:8100
- Frontend dashboard: http://localhost:3000

Without Docker, each service can run directly — see the README in
`backend/`, `drone-gateway/`, and `frontend/`.

## What is real / what is simulated

| Capability | Status |
|---|---|
| Drone fleet | **Simulated.** No physical hardware anywhere in this repo. |
| VLM perception | Real model inference (open model, runs on CPU or GPU). |
| Multi-agent orchestration (LangGraph/AutoGen/CrewAI) | Real, runs end-to-end locally. |
| RAG over SOPs | Real vector search (Milvus Lite by default, Milvus standalone or Pinecone as alternates). |
| Persistent memory | Real (SQLite-backed), demonstrated across missions. |
| GPU benchmarks | *Pending — see `docs/benchmarks.md`; this environment has no GPU.* |
| LangSmith tracing | *Pending user's `LANGSMITH_API_KEY`.* |
| Pinecone live run | *Pending user's `PINECONE_API_KEY`.* |
| GCP deployment | *Pending `gcloud` auth — see `deploy/gcp/`.* |

This table is a summary; the authoritative, evidence-backed version is in
the final report at the bottom of this README (added once all phases are
verified) and in `docs/limitations.md`.

## License

Code is MIT-licensed (see `LICENSE`). The sampled imagery under
`data/images/` and `data/labels/` is CC BY-NC-SA 3.0 (non-commercial) —
see `docs/data.md`.
