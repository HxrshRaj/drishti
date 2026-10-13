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
- [`deploy/`](deploy) — GCP Cloud Run deployment scripts, and [`deploy/aws/`](deploy/aws): a serverless AWS version of the perception step (S3, Lambda, Bedrock, DynamoDB, API Gateway; CDK).

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
| Azure serverless pipeline (Blob Storage, Functions, Azure OpenAI, Table Storage) | Code, Pulumi program and 24 tests written. Storage tested against the Azurite emulator, infra against mocked Azure; *not deployed, real Azure OpenAI not exercised. See `deploy/azure/`.* |
| GCP deployment | *Pending `gcloud` auth — see `deploy/gcp/`.* |
| AWS serverless pipeline (S3, Lambda, Bedrock, DynamoDB, API Gateway) | Code, CDK stack and 23 tests written. Tested with emulated S3/DynamoDB and a fake Bedrock client; *not deployed, real Bedrock not exercised. See `deploy/aws/`.* |

This table is a summary; the authoritative, evidence-backed version is the
**Final report** section at the bottom of this README, and `docs/limitations.md`.

## License

Code is MIT-licensed (see `LICENSE`). The sampled imagery under
`data/images/` and `data/labels/` is CC BY-NC-SA 3.0 (non-commercial) —
see `docs/data.md`.

---

## Final report

### Verified and safe to claim (with evidence)

| Capability | Evidence |
|---|---|
| Simulated drone fleet, real HTTP API, failure injection | `drone-gateway/tests/test_fleet.py` — 9/9 passing against the real sampled dataset. `POST /admin/inject_failure` exercised for real (not mocked) in `backend/tests/test_mission_graph.py`. |
| Licensed aerial imagery, documented provenance | `docs/data.md` — 350 images sampled from VisDrone2019-DET, CC BY-NC-SA 3.0, committed to the repo. |
| Two-stage VLM perception, schema-validated JSON, retry + parse-failure tracking | `docs/benchmarks.md` — 20-image hand-verified run, 0% parse failure rate, real latency (p50 32.1s / p95 50.8s on CPU). The single-stage design's failure mode is documented with actual raw model outputs. |
| RAG over the SOP corpus | `docs/benchmarks.md` — recall@1 92.9%, recall@5 100% over a 28-query hand-labeled set, real run (`benchmarks/eval_retrieval.py`). |
| Persistent memory across missions | `backend/tests/test_memory_repository.py::test_second_mission_sees_first_missions_open_findings` — passing. |
| LangGraph mission workflow with checkpointed pause/resume | `backend/tests/test_mission_graph.py` — 5/5 passing, real HTTP calls to a real gateway subprocess, real interrupt()/Command(resume=...) cycle. |
| AutoGen Perception-vs-Verifier exchange | `backend/app/agents/verifier.py`, exercised in a real end-to-end mission run (see below) — real two-agent message exchange logged verbatim to the audit trail. |
| CrewAI Analyst + Report Writer crew, real pandas tool | `backend/tests/test_reporting_tools.py` (tool logic) + a real end-to-end mission run producing a real (imperfect — see Limitations) narrative report, persisted and viewable in the frontend. |
| Safety policy + approval gates | `backend/tests/test_safety_gate.py` — 14/14 passing, including the required "blocked, then approved" test. |
| Fallback protocols (low confidence, drone offline, capture timeout) | `backend/tests/test_mission_graph.py` — all three exercised via real failure injection, not mocked exceptions. |
| Structured JSON audit logging (works with zero credentials) | `backend/tests/test_observability.py` — every audit event emits a structured log line. |
| Full end-to-end mission (real backend + real gateway + real frontend) | Run live during development: mission `fcbdcdf4929a4841` (harbor-industrial-park) — planned → dispatched → captured → perceived → verified (agree) → recorded → reported → completed, ~7 minutes wall clock, viewable at `/missions/fcbdcdf4929a4841` once the stack is running. |
| Operator dashboard (Next.js 16) | All 5 pages (missions, mission detail, findings, approvals, metrics) verified rendering real backend data in a real browser session; `npm run build` and `npm run lint` both clean. |
| CI (lint + tests + eval, CPU) | `.github/workflows/ci.yml` — runs backend/gateway/benchmarks tests, ruff, and the perception+retrieval evals on every push. |

### Simulated or limited (stated plainly, not hidden)

- **The drone fleet is 100% simulated** — see the "Simulated fleet" badge on every page of the dashboard. No physical hardware anywhere.
- **Domain mismatch**: VisDrone is a traffic/pedestrian surveillance dataset, not a structural-defect inspection dataset — findings are object-presence observations, not crack/corrosion detection. See `docs/data.md`.
- **CrewAI report quality with the local 0.5B model is real but rough** — the live end-to-end run's report includes ungrounded filler ("checking for any signs of tampering") and repeats sections. The independently pandas-computed summary is always included alongside it precisely because the LLM's narrative isn't fully trustworthy on its own — see `docs/limitations.md`.
- **The parity report's "100% accuracy, no flags" result is a weak signal**, not a clean bill of health — explained honestly in `docs/bias-report.md` (small, vehicle-heavy sample; most groups below the confidence threshold).
- **AutoGen's verifier doesn't do live tool-calls** — SOP/memory retrieval is a Python pre-step, not the LLM calling a tool live (a deliberate trade-off given the local model's function-calling reliability — see `docs/architecture.md`).
- **Resizing input images doesn't meaningfully speed up inference** — a real, slightly counterintuitive CPU benchmark finding, documented rather than omitted.

### Pending: needs credentials or hardware this environment doesn't have

- **GPU benchmark numbers** — `benchmarks/colab_bench.ipynb` is written and ready to run on a free Colab/Kaggle GPU; not run here (no GPU in this environment).
- **Pinecone live run** — `app/vectorstore/pinecone_store.py` is implemented against the current Pinecone SDK; not exercised without `PINECONE_API_KEY`.
- **LangSmith live traces** — `app/observability/langsmith.py` activates automatically once `LANGSMITH_API_KEY` is set; not exercised here without one.
- **GCP deployment** — `deploy/gcp/deploy.sh` is written and ready to run; not run here (no `gcloud` installed/authenticated in this environment).
- **Frontend hosting (Vercel or similar)** — not attempted for the same reason.
- **AutoGen with a hosted Anthropic model** — falls back to the local model or `OPENAI_API_KEY`; the `autogen-ext[anthropic]` extra isn't installed (see `docs/limitations.md`).

This is the one point in the build where a human check-in is genuinely needed: the items above require credentials or hardware (a GPU, cloud auth, API keys) that don't exist in this build environment. Everything else was built and verified end-to-end without stopping.
