# agentkit: agent harness, middleware, tracing and evals

`backend/app/agentkit/` is a small, framework-independent agent harness plus the tooling
around it. It exists to make the parts of an agent that usually stay hidden inside a
framework explicit, testable and measurable.

## What is in it

| Piece | File | What it does |
|---|---|---|
| Execution loop | `harness.py` | model call -> validated tool calls -> results -> repeat; step cap; token accounting; checkpoint after every step |
| Middleware | `middleware.py` | `ToolRetry` (exponential backoff, transient errors only), `ErrorToMessage` (failures become safe results, no stack traces to the model), `ApprovalGate` (human-in-the-loop pause), `ContextTrim` (budgeted context that never orphans a tool result) |
| Tool safety | `harness.py`, `types.py` | Pydantic argument validation, per-tool permissions, unknown-tool handling |
| Pause and resume | `checkpoint.py` | SQLite and MongoDB checkpoint stores; a run paused for approval resumes in a fresh harness |
| Tracing | `tracing.py` | OpenTelemetry spans for runs, model calls and tool calls (latency, tokens, errors); `traced_node` wraps the existing LangGraph mission nodes |
| DeepAgents | `deep_agent.py` | The same tools as a DeepAgents agent with `interrupt_on` for refunds and a tracing middleware |
| Model adapters | `llm_openai.py` | OpenAI, Azure OpenAI and any OpenAI-compatible server, with tool calling |
| Evals | `evals/` | 23-case dataset, tool-selection precision/recall, argument accuracy, task completion, hallucination rate, forbidden-tool rate, tokens, latency; baseline + regression gate; MLflow logging |

## Sending traces to MLflow, Langfuse or LangSmith

Spans export over OTLP/HTTP when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

```bash
# MLflow >= 3 (verified, see below)
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://127.0.0.1:5000/v1/traces
export OTEL_EXPORTER_OTLP_HEADERS="x-mlflow-experiment-id=<experiment id>"

# Langfuse (not run here: needs a Langfuse project and keys)
export OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/public/otel
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic <base64 public:secret>"
```

## Running the evals

```bash
cd backend
python -m app.agentkit.evals.runner                    # reference model, gated against baseline.json
python -m app.agentkit.evals.runner --mlflow           # also logs metrics to MLflow
OPENAI_API_KEY=... python -m app.agentkit.evals.runner --model openai
AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_DEPLOYMENT=... AZURE_OPENAI_API_KEY=... \
  python -m app.agentkit.evals.runner --model azure
```

The exit code is 1 when any metric regresses past the baseline tolerance, so it can gate CI.

## What is verified and what is not

| Claim | Evidence |
|---|---|
| Harness validation, retry, error handling, approval pause/resume, step cap, context trim | `tests/agentkit/test_harness.py` |
| Pause in one harness, resume in another from a SQLite file | `test_approval_pauses_then_resumes_from_checkpoint_in_a_new_harness` |
| MongoDB checkpoint store | `test_harness.py`, run against **mongomock**, not a real MongoDB server |
| Azure OpenAI request shape (URL, `api-key`, `api-version`, no `model` in body) | `test_llm_openai.py`, against an HTTP mock transport; **never called a real Azure endpoint** |
| DeepAgents agent, refund interrupt, approve and reject | `test_deep_agent.py`, with a scripted chat model |
| OTel spans for runs, model calls, tool calls, LangGraph nodes | `test_harness.py`, `test_mission_tracing.py` |
| Spans reach MLflow over OTLP | Run by hand against a local `mlflow server`: one trace with `agent.run`, `agent.model_call` x2, `agent.tool_call` x2 came back from `mlflow.search_traces`. Not automated in CI |
| Eval metrics detect real failures | `test_evals.py` runs three deliberately degraded models (wrong arguments, over-eager tool use, invented figures); the gate catches each |
| Eval metrics logged to MLflow | `test_metrics_are_logged_to_mlflow` (SQLite backend) |

Limits, stated plainly:

* The committed baseline is for `ReferenceModel`, a rule-based stand-in that reads the task with
  regexes. It scores 100% by construction. It proves the pipeline, metrics and gate work; it says
  nothing about how any real LLM performs. Run `--model openai|azure|ollama` for that.
* Token counts for the reference model are estimates (characters / 4).
* The Azure OpenAI wiring in the AutoGen verifier and CrewAI report crew is written but not run
  (those packages need credentials and a real Azure resource).
* Langfuse and LangSmith export use the same OTLP path but were not run here.
* The drone fleet in the rest of this project is still simulated.
