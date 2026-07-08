#!/usr/bin/env bash
# VAAYU deployment (Cloud Run + Scheduler). Idempotent; re-runnable.
# Costs stay in free tier: service min-instances=0 (no idle), one hourly job,
# one scheduler trigger (first 3 free). See docs/BUDGET.md.
set -euo pipefail

PROJ=main-aura-398409
REGION=asia-south1
IMAGE="$REGION-docker.pkg.dev/$PROJ/vaayu/app:latest"
SA="229692962627-compute@developer.gserviceaccount.com"   # default compute SA (has roles/editor)

# 1. APIs (once)
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com --project "$PROJ"

# 2. Artifact Registry repo (once)
gcloud artifacts repositories create vaayu --repository-format=docker \
  --location="$REGION" --project "$PROJ" || true

# 3. Secret: CPCB data.gov.in key (create once; add versions on rotation)
#    printf '%s' "$DATA_GOV_IN_API_KEY" | gcloud secrets create DATA_GOV_IN_API_KEY --data-file=- --project "$PROJ"

# 4. Build + push image
gcloud builds submit --tag "$IMAGE" --project "$PROJ"

# 5. API service (public UI + endpoints). No secrets needed (BigQuery via ADC).
gcloud run deploy vaayu-api \
  --image "$IMAGE" --region "$REGION" --project "$PROJ" \
  --allow-unauthenticated --min-instances 0 --max-instances 2 \
  --memory 512Mi --cpu 1 --port 8080 \
  --set-env-vars "GCP_PROJECT_ID=$PROJ,BQ_DATASET=vaayu"

# 6. Hourly pipeline Job (same image, command overridden). CPCB key from Secret Manager.
gcloud run jobs deploy vaayu-hourly \
  --image "$IMAGE" --region "$REGION" --project "$PROJ" \
  --command python --args pipeline.py \
  --memory 1Gi --cpu 1 --task-timeout 1800 --max-retries 1 \
  --set-env-vars "GCP_PROJECT_ID=$PROJ,BQ_DATASET=vaayu" \
  --set-secrets "DATA_GOV_IN_API_KEY=DATA_GOV_IN_API_KEY:latest"

# 7. Cloud Scheduler -> run the job hourly (SA needs run.invoker; editor covers it)
JOB_RUN_URI="https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJ/jobs/vaayu-hourly:run"
gcloud scheduler jobs create http vaayu-hourly-trigger \
  --project "$PROJ" --location "$REGION" --schedule "0 * * * *" \
  --uri "$JOB_RUN_URI" --http-method POST \
  --oauth-service-account-email "$SA" || \
gcloud scheduler jobs update http vaayu-hourly-trigger \
  --project "$PROJ" --location "$REGION" --schedule "0 * * * *" \
  --uri "$JOB_RUN_URI" --http-method POST \
  --oauth-service-account-email "$SA"

echo "Deployed. API URL:"
gcloud run services describe vaayu-api --region "$REGION" --project "$PROJ" --format="value(status.url)"
