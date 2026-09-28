# Limitations

Honest, specific list of what this project does not do well, or does not
do at all, and why. Cross-referenced from the final report.

## Perception model capability (256M-parameter VLM)

- **A single-prompt "look and return this JSON schema" approach fails.**
  Verified directly: `HuggingFaceTB/SmolVLM-256M-Instruct` prompted to
  return the finding JSON in one shot reliably copied a few-shot example's
  *content* verbatim regardless of the actual image, instead of describing
  what it saw — while the same model, prompted only for an open-ended
  caption, produced genuinely image-grounded, different output per image.
  See `docs/architecture.md` and `docs/benchmarks.md` for the raw outputs
  from both versions. The shipped pipeline is two-stage (caption, then a
  separate text LLM structures the caption into JSON) specifically to work
  around this — it is a real capacity limit at this model size, not a
  prompt bug, and a larger VLM (7B+ class) would very likely not need the
  split.
- **The structuring stage can still under- or over-generalize** the
  caption's content (e.g. folding "buildings, vehicles, poles" into a
  finding_type like `building_and_vehicle_presence` rather than the
  suggested `vehicle_presence`). finding_type is deliberately an open
  string, not a closed enum, partly because of this — see
  `app/perception/schemas.py`.
- **Domain mismatch, stated in `docs/data.md`:** the licensed dataset
  (VisDrone2019-DET) is traffic/pedestrian surveillance, not structural
  building/infrastructure inspection. Findings are framed as object/
  presence observations, not defect detection (no crack/corrosion
  labels exist in this dataset to train or evaluate against).

## AutoGen verifier

- The Verifier agent's SOP/memory retrieval is a Python pre-step injected
  as context, not a live LLM tool-call — the local model has no native
  function-calling protocol to rely on for a safety-relevant check. See
  `docs/architecture.md`, seam #1.
- AutoGen's own Anthropic client extra (`autogen-ext[anthropic]`) is not
  installed, so `ANTHROPIC_API_KEY` upgrades LangGraph and CrewAI but not
  the AutoGen verifier, which stays on the local model or `OPENAI_API_KEY`.

## CrewAI reporting

- Whether the local 0.5B model reliably drives the Analyst agent's real
  pandas tool call is reported from an actual observed run in
  `docs/benchmarks.md`, not assumed. `generate_report()` always also
  returns an independently pandas-computed summary
  (`compute_findings_summary`) alongside whatever the crew's LLM produced,
  so the report's numbers are never solely dependent on the LLM's tool-call
  succeeding.
- **Real observed report quality is rough, and that's shown, not hidden.**
  A live end-to-end mission run (`fcbdcdf4929a4841`, viewable in the
  dashboard once the stack is running) produced a report whose narrative
  includes ungrounded filler not supported by the findings data ("This
  includes checking for any signs of tampering or unauthorized access to
  the report") and repeats the Findings Table / Mission Summary sections
  twice with slightly different wording. The structured data underneath
  (finding type, severity, confidence, the pandas-computed summary) is
  correct; the 0.5B model's prose is not fully reliable, which is exactly
  why `report_summary` (the independently computed ground truth) is stored
  and displayed alongside `report_text` rather than the narrative being
  the only source of truth — see the Report section of
  `frontend/src/app/missions/[id]/page.tsx`. A hosted model
  (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`) would very likely produce a
  cleaner narrative; this wasn't verified live since no such key is
  configured in this environment.

## Performance / hardware

- **No GPU was available in the environment this project was built in**
  (confirmed: no `nvidia-smi`). Every real number in `docs/benchmarks.md`
  is a genuine CPU measurement; the GPU comparison table is marked
  "pending user run" with a ready-to-run Colab notebook
  (`benchmarks/colab_bench.ipynb`), not filled with invented numbers.
- CPU inference is slow enough (see `docs/benchmarks.md` for exact
  per-call latency) that `MissionGraphDeps.max_waypoints` defaults to 3,
  not a full site sweep, to keep one real end-to-end mission run tractable.
- 4-bit/8-bit quantization via `bitsandbytes` is primarily CUDA-accelerated;
  its CPU path is not meaningfully faster here and is not part of the CPU
  benchmark table for that reason (documented, not silently skipped).

## Vector store / naming

- `VECTOR_STORE_URI`, not `MILVUS_URI` — pymilvus reads the latter env var
  name itself at import time for its own default connection and expects an
  http(s) URI, which crashes on import against a Milvus Lite file path. See
  the comment in `backend/app/config.py`.

## Pending: needs credentials or hardware this environment does not have

- **GPU benchmark numbers** — `benchmarks/colab_bench.ipynb`, run on a free
  Colab/Kaggle GPU.
- **Pinecone live run** — implemented (`app/vectorstore/pinecone_store.py`),
  not exercised without `PINECONE_API_KEY`.
- **LangSmith live traces** — tracing config exists
  (`app/observability/langsmith.py`) and activates automatically once
  `LANGSMITH_API_KEY` is set; not exercised here without one.
- **GCP deployment** — `deploy/gcp/deploy.sh` is ready to run; not run here
  (no `gcloud` in this environment).
- **Frontend hosting (Vercel or similar)** — not attempted for the same
  reason.
