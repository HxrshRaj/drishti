#!/usr/bin/env bash
# Deploys Drishti's backend and drone-gateway to Cloud Run, and creates a
# Cloud Storage bucket for imagery/artifacts. NOT run automatically by
# anything in this repo — the build environment this project was built in
# has no `gcloud` installed/authenticated (see docs/limitations.md), so
# this script is verified ready-to-run but not verified to have actually
# deployed. Run it yourself once you have a GCP project and are logged in:
#
#   gcloud auth login
#   export GCP_PROJECT_ID=your-project-id
#   export GCP_REGION=us-central1          # optional, defaults below
#   export GCS_BUCKET=your-bucket-name     # optional, derived below
#   bash deploy/gcp/deploy.sh
set -euo pipefail

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID first (see .env.example)}"
GCP_REGION="${GCP_REGION:-us-central1}"
GCS_BUCKET="${GCS_BUCKET:-${GCP_PROJECT_ID}-drishti-artifacts}"

echo "== Drishti GCP deploy =="
echo "Project: $GCP_PROJECT_ID  Region: $GCP_REGION  Bucket: $GCS_BUCKET"

gcloud config set project "$GCP_PROJECT_ID"

echo "-- Enabling required APIs --"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com

echo "-- Creating Cloud Storage bucket for imagery/artifacts (idempotent) --"
gsutil mb -l "$GCP_REGION" "gs://${GCS_BUCKET}" 2>/dev/null || echo "bucket already exists, continuing"
gsutil -m rsync -r ../../data/images "gs://${GCS_BUCKET}/data/images"
gsutil -m rsync -r ../../data/labels "gs://${GCS_BUCKET}/data/labels"
gsutil -m rsync -r ../../data/sops "gs://${GCS_BUCKET}/data/sops"

echo "-- Deploying drone-gateway (simulated fleet) to Cloud Run --"
gcloud run deploy drishti-drone-gateway \
  --source ../../drone-gateway \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --set-env-vars "DATA_IMAGES_DIR=/data/images,DATA_LABELS_FILE=/data/labels/labels.jsonl" \
  --memory 512Mi --cpu 1

GATEWAY_URL=$(gcloud run services describe drishti-drone-gateway --region "$GCP_REGION" --format='value(status.url)')
echo "Gateway deployed at: $GATEWAY_URL"

echo "-- Deploying backend to Cloud Run --"
echo "   NOTE: perception (VLM inference) defaults to CPU here. For GPU"
echo "   inference in the cloud you need a Cloud Run GPU-enabled service"
echo "   (requires quota) or a separate GPU host — see docs/benchmarks.md"
echo "   and docs/limitations.md for the Live vs Replay modes."
gcloud run deploy drishti-backend \
  --source ../../backend \
  --region "$GCP_REGION" \
  --allow-unauthenticated \
  --set-env-vars "DEVICE=cpu,DRONE_GATEWAY_URL=${GATEWAY_URL},VECTOR_STORE_BACKEND=milvus_lite,GCS_BUCKET=${GCS_BUCKET}" \
  --memory 4Gi --cpu 2 --timeout 300

BACKEND_URL=$(gcloud run services describe drishti-backend --region "$GCP_REGION" --format='value(status.url)')
echo "Backend deployed at: $BACKEND_URL"

echo "== Done. Point the frontend's NEXT_PUBLIC_API_BASE_URL at: $BACKEND_URL =="
