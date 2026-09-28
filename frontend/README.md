# Drishti Operator Dashboard

Next.js 16 (App Router) dashboard for the Drishti backend: mission list +
live mission view with the agent timeline, a findings gallery, the
human-in-the-loop approval queue, and a metrics page reading real
benchmark/eval results.

## Run locally

Needs the backend (port 8000) and drone-gateway (port 8100) running first
— see `../backend/README.md` and `../drone-gateway/README.md`.

```bash
cp .env.example .env.local   # already points at localhost:8000 / :8100
npm install
npm run dev
```

http://localhost:3000

## Pages

- `/` — mission list, start-mission form.
- `/missions/[id]` — live mission view: agent timeline (polls
  `GET /missions/{id}/audit` every 4s), findings, and the approval panel
  when a mission is paused at a human-approval interrupt.
- `/findings` — gallery across all missions.
- `/approvals` — the pending-approval queue (SOP-004).
- `/metrics` — real benchmark/eval/parity numbers, read live from
  `backend/app/observability/metrics_router.py`, which serves whatever is
  actually in `benchmarks/results/` — "Not generated yet" if a script
  hasn't been run, never a placeholder number.

## Status badges

The header always shows **Simulated fleet** (this is never a claim about
real hardware) and **Live** / **Replay** — set via
`NEXT_PUBLIC_INFERENCE_MODE`, which must match how the backend is actually
configured (see `../deploy/gcp/README.md`).
