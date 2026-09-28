# Architecture

Drishti is a full-stack agentic pipeline for aerial site inspection, built
around a deliberate choice: **use a different framework for each job it is
actually best at, and be honest about the seams where they hand off.** The
drone fleet is entirely simulated — see `drone-gateway/`.

## Why each framework is where it is

| Concern | Framework | Why here, not elsewhere |
|---|---|---|
| Mission-level control flow, checkpointed pause/resume | **LangGraph** | It's a state machine with first-class `interrupt()`/`Command(resume=...)` and a pluggable checkpointer (SqliteSaver here) — exactly what SOP-004's approval gates need: pause a *specific* mission at a *specific* node and resume it later, possibly in a different process. |
| Perception-vs-Verifier agent-to-agent challenge | **AutoGen** (`autogen-agentchat`) | This is specifically the "two agents talk to each other and one challenges the other" pattern AutoGen's `RoundRobinGroupChat` is built for. LangGraph could simulate it with two nodes, but AutoGen gives real `AssistantAgent` objects exchanging real messages with named sources, which is what SOP-007 asks to be logged verbatim. |
| Turning accepted findings into a report | **CrewAI** | Role-based crews (Analyst, Report Writer) with sequential task handoff and a real tool call map directly onto SOP-009's report structure — Analyst computes, Writer narrates, and CrewAI's `context=[analyst_task]` is exactly "the writer sees the analyst's output." |
| Everything in between (RAG, memory, safety policy, HTTP calls to the gateway) | **Plain Python / FastAPI / SQLAlchemy** | No framework needed. Reaching for LangChain retrievers or an agent framework for "query a vector store" or "write a row to SQLite" would be the wrong tool — see the project's own instruction to not add abstraction beyond what's needed. |

## Model architecture (why two small models, why two stages)

No GPU is available in this environment (confirmed: no `nvidia-smi`),
so every model here had to run real inference on CPU. Two small, permissively
licensed models are used:

- **Perception (vision):** `HuggingFaceTB/SmolVLM-256M-Instruct` (Apache-2.0).
- **Agent reasoning / structuring (text):** `Qwen/Qwen2.5-0.5B-Instruct`
  (Apache-2.0), served behind a small OpenAI-compatible `/v1/chat/completions`
  endpoint inside the backend (`app/llm/openai_compat_router.py`) so
  LangChain's `ChatOpenAI`, AutoGen's `OpenAIChatCompletionClient`, and
  CrewAI's `LLM` can all point at the same local model through one
  `base_url` override — the same pattern used to point these frameworks at
  a self-hosted vLLM/TGI server in production. If `ANTHROPIC_API_KEY` or
  `OPENAI_API_KEY` is set, `app/llm/provider.py` upgrades agent reasoning to
  that hosted provider instead; the local model exists so the whole system
  runs with zero credentials.

**Perception is two stages, not one — and this was discovered, not
assumed.** The first design was a single VLM call: show the image, ask for
the JSON schema directly. That worked for open-ended captioning (verified
grounded — different images produced different, plausible captions) but
**failed** for the JSON-constrained version of the same prompt: the 256M
model reliably copied a few-shot example's *content* verbatim regardless of
the actual image, rather than describing what it saw. This is documented
with the actual raw outputs in `docs/benchmarks.md`. The fix: stage 1 asks
the VLM for a free-text caption only (grounded, verified); stage 2 hands
that caption to the local text LLM to structure into the JSON schema — a
text-only task the small model is measurably better at than combining
vision grounding with strict formatting in one shot. This is a real
capacity limit of a 256M-parameter VLM, not a prompt bug, and a larger
model (documented in `docs/limitations.md`) would likely not need this
split.

## Known seams (stated honestly, not hidden)

1. **The Verifier agent's RAG/memory retrieval is a Python pre-step, not a
   live LLM tool-call.** AutoGen and CrewAI both support agents calling
   tools live, but that relies on the model client reliably emitting
   structured tool-call output — something a raw local Qwen2.5-0.5B
   text-completion endpoint (no native function-calling protocol) cannot be
   trusted to do for a safety-relevant check. So `app/agents/verifier.py`
   retrieves SOP context and site memory in Python *before* starting the
   AutoGen exchange and injects it as text context; the LLM's job is
   narrowed to reasoning over given evidence, not fetching it. The CrewAI
   Analyst agent *is* wired with a real tool (`findings_summary_tool`,
   backed by real pandas) — whether the local 0.5B model successfully
   drives that tool call in practice is reported honestly in
   `docs/benchmarks.md`, not asserted.
2. **AutoGen's Anthropic client extra isn't installed.** `ANTHROPIC_API_KEY`
   upgrades LangGraph nodes and the CrewAI crew (both have native Anthropic
   support), but the AutoGen verifier falls back to the local model or
   `OPENAI_API_KEY` — see `app/agents/verifier.py::_make_model_client`.
3. **`MILVUS_URI` is a reserved name.** pymilvus reads that exact
   environment variable itself for its own default connection, which
   collides with a Milvus Lite local-file-path default. This project's
   equivalent setting is `VECTOR_STORE_URI` instead — see the comment in
   `backend/app/config.py`.
4. **Waypoint counts per mission are small by default
   (`MAX_WAYPOINTS_DEFAULT = 3`).** Each waypoint runs a real VLM call and a
   real two-agent AutoGen exchange, both real CPU inference — see the
   measured per-call latency in `docs/benchmarks.md` before assuming a
   10-waypoint mission finishes quickly on CPU.

## Data flow for one waypoint

```
LangGraph "dispatch" ──HTTP──▶ drone-gateway /goto
LangGraph "capture"  ──HTTP──▶ drone-gateway /capture ──▶ image (licensed dataset)
LangGraph "perceive" ──▶ VLM caption ──▶ local LLM structuring ──▶ VLMFinding (JSON)
LangGraph "verify"   ──▶ AutoGen: PerceptionAgent states finding,
                          VerifierAgent checks it against RAG'd SOPs + memory
LangGraph "decide"   ──▶ safety policy (app/safety/policy.py) classifies risk
                          risk=high ──▶ interrupt() ──▶ operator approves/rejects
                                        via POST /missions/{id}/decide
                          risk=low  ──▶ recorded immediately (app/memory/repository.py)
(loop to next waypoint, or)
LangGraph "report"   ──▶ CrewAI Analyst + Report Writer ──▶ inspection report
```

Every step above logs to the audit trail (`app/memory/repository.py::log_audit_event`,
SOP-014) with the mission id, so `GET /missions/{id}/audit` reconstructs the
full trace of one mission — including the interrupt and the operator's
decision — for the operator dashboard's timeline view.
