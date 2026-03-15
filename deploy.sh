#!/bin/bash
# Next Live — One-command Cloud Run deployment
# Usage: ./deploy.sh

set -euo pipefail

PROJECT_ID="next-live-agent"
REGION="us-central1"
SERVICE_NAME="next-live-agent"

echo "=== Deploying Next Live to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Ensure correct project
gcloud config set project "${PROJECT_ID}"

# Deploy to Cloud Run from source
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --timeout 3600 \
  --cpu 2 \
  --memory 4Gi \
  --min-instances 1 \
  --max-instances 20 \
  --concurrency 80 \
  --no-cpu-throttling \
  --session-affinity \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=True"

echo ""
echo "=== Deployment complete ==="

# Get and display service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format='value(status.url)')
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Open ${SERVICE_URL} in Chrome, select next25_agent, click mic, say hey!"
