# GCP Deployment

Status: **scripts are ready to run; not yet actually deployed.** The
environment this project was built in has no `gcloud` CLI installed or
authenticated, so this is listed under "Pending: needs credentials" in the
final report rather than claimed as done. See `docs/limitations.md`.

## What this deploys

- `drishti-drone-gateway` → Cloud Run (simulated fleet service)
- `drishti-backend` → Cloud Run (perception + orchestration + agents + RAG)
- A Cloud Storage bucket holding the sampled imagery, labels, and SOP corpus

## Prerequisites

1. A GCP project with billing enabled.
2. `gcloud` CLI installed and authenticated: `gcloud auth login`.
3. `gsutil` (ships with `gcloud`).

## Steps

```bash
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=us-central1          # optional
export GCS_BUCKET=your-bucket-name     # optional
bash deploy/gcp/deploy.sh
```

This runs `gcloud run deploy --source` for both services (Cloud Build
builds each Dockerfile server-side — no local Docker required) and syncs
`data/` to Cloud Storage.

## Live vs Replay inference

Cloud Run's standard tiers are CPU-only. Real-time VLM inference on CPU in
the cloud will be slow for the same reason it's slow locally (see
`docs/benchmarks.md`) — there was no GPU available to benchmark a cloud GPU
path from this environment either. Two modes are supported and must be
labeled honestly wherever inference results are shown (README, frontend
badge):

- **Live**: the backend's own `/perception/analyze` endpoint runs real
  model inference, wherever it's deployed (CPU here; point `VLM_MODEL_ID`
  / a GPU-backed Cloud Run service with GPU quota at it for faster live
  inference).
- **Replay**: serves cached real outputs captured during this project's
  own benchmark runs (`benchmarks/results/`) instead of running the model
  per-request. Never presented as live inference — see the frontend's
  "Simulated fleet" / "Live vs Replay" badge (Phase 7).

## Frontend

Deploy `frontend/` separately (Vercel or any static/Node host) with
`NEXT_PUBLIC_API_BASE_URL` pointed at the deployed backend's Cloud Run URL.
Not attempted here for the same reason: no deployment credentials in this
environment.
