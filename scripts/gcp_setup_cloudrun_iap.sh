#!/usr/bin/env bash
# Provision Cloud Run v2 Direct IAP reverse-proxy ingress fronting the private GCE hub VM (ACE-WS-04).
# Eliminates manual Custom OAuth Client setup (Error 604) and 15-min managed SSL waits while keeping
# Classic HTTPS LB (scripts/gcp_setup_lb.sh) available for >1h uninterrupted streaming sessions.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
if [ ! -f .env ]; then echo ".env missing — copy .env.example first" >&2; exit 1; fi
set -a; . ./.env; set +a

: "${GOOGLE_CLOUD_PROJECT:?set in .env}"
: "${VM_NAME:?add to .env}"
: "${VM_ZONE:?add to .env}"

ACTIVE_ACCT="$(gcloud config get-value account 2>/dev/null || true)"
export CLOUDSDK_CORE_ACCOUNT="${SSH_USER:-${GCP_ACCOUNT:-${ACTIVE_ACCT:?set GCP_ACCOUNT or run gcloud auth login}}}"
IAP_USERS="${IAP_USERS:-user:${CLOUDSDK_CORE_ACCOUNT}}"
NAME_PREFIX="${NAME_PREFIX:-antigravity-web}"
PROJECT="$GOOGLE_CLOUD_PROJECT"

# Auto-detect actual VM zone if instance already exists
DETECTED_ZONE=$(gcloud --quiet --project="$PROJECT" compute instances list \
  --filter="name=${VM_NAME}" --format="value(zone)" 2>/dev/null | head -n 1 || true)
if [ -n "$DETECTED_ZONE" ]; then
  VM_ZONE="$DETECTED_ZONE"
fi
REGION="${VM_ZONE%-*}"

echo "→ Enabling Cloud Run, Artifact Registry, Cloud Build, and IAP APIs..."
gcloud --quiet --project="$PROJECT" services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iap.googleapis.com \
  compute.googleapis.com 2>/dev/null || true

VM_INTERNAL_IP=$(gcloud --quiet --project="$PROJECT" compute instances describe "$VM_NAME" \
  --zone="$VM_ZONE" --format='value(networkInterfaces[0].networkIP)')
if [ -z "$VM_INTERNAL_IP" ]; then
  echo "✖ Could not resolve internal IP for VM $VM_NAME in $VM_ZONE." >&2
  exit 1
fi
echo "  Resolved private hub target: http://${VM_INTERNAL_IP}:8080"

# Allow Direct VPC Egress traffic from the subnet to the VM's Nginx port :8080
echo "→ Configuring VPC firewall rules (IAP SSH + Direct VPC Egress -> :8080)..."
gcloud --quiet --project="$PROJECT" compute firewall-rules create "${NAME_PREFIX}-allow-iap" \
  --network="${NAME_PREFIX}-vpc" \
  --direction=INGRESS --action=allow --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 \
  --target-tags="${NAME_PREFIX}" 2>/dev/null || true

SUBNET_CIDR=$(gcloud --quiet --project="$PROJECT" compute networks subnets describe "${NAME_PREFIX}-subnet" \
  --region="$REGION" --format='value(ipCidrRange)' 2>/dev/null || echo "10.0.1.0/24")
gcloud --quiet --project="$PROJECT" compute firewall-rules create "${NAME_PREFIX}-allow-cloudrun-egress" \
  --network="${NAME_PREFIX}-vpc" \
  --direction=INGRESS --action=allow --rules=tcp:8080 \
  --source-ranges="${SUBNET_CIDR}" \
  --target-tags="${NAME_PREFIX}" --priority=900 2>/dev/null || true

# Ensure Artifact Registry repository & build stateless Nginx proxy container
AR_REPO="${NAME_PREFIX}-proxy-repo"
PROXY_SVC="${NAME_PREFIX}-proxy"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/cloudrun-iap-proxy:v3.10.0"

echo "→ Ensuring Artifact Registry repo ${AR_REPO} in ${REGION}..."
gcloud --quiet --project="$PROJECT" artifacts repositories describe "$AR_REPO" --location="$REGION" >/dev/null 2>&1 \
  || gcloud --quiet --project="$PROJECT" artifacts repositories create "$AR_REPO" \
       --repository-format=docker --location="$REGION" --description="Antigravity Web Hub Cloud Run Direct IAP Proxy"

# Ensure Cloud Build & Compute SAs can write/read Artifact Registry
PROJECT_NUM=$(gcloud --quiet projects describe "$PROJECT" --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"
CB_SA="${PROJECT_NUM}@cloudbuild.gserviceaccount.com"
RUNTIME_SA_EMAIL="${NAME_PREFIX}-runtime@${PROJECT}.iam.gserviceaccount.com"
for sa in "$COMPUTE_SA" "$CB_SA"; do
  gcloud --quiet --project="$PROJECT" artifacts repositories add-iam-policy-binding "$AR_REPO" \
    --location="$REGION" --member="serviceAccount:${sa}" --role="roles/artifactregistry.writer" >/dev/null 2>&1 || true
done
gcloud --quiet --project="$PROJECT" artifacts repositories add-iam-policy-binding "$AR_REPO" \
  --location="$REGION" --member="serviceAccount:${RUNTIME_SA_EMAIL}" --role="roles/artifactregistry.reader" >/dev/null 2>&1 || true
gcloud --quiet --project="$PROJECT" projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${COMPUTE_SA}" --role="roles/logging.logWriter" >/dev/null 2>&1 || true

echo "→ Building Cloud Run IAP Proxy image (${IMAGE_URI})..."
gcloud --quiet --project="$PROJECT" builds submit "${REPO_ROOT}/src/cloudrun_iap_proxy" \
  --region="$REGION" --tag="$IMAGE_URI"

RUNTIME_SA_EMAIL="${NAME_PREFIX}-runtime@${PROJECT}.iam.gserviceaccount.com"
echo "→ Deploying Cloud Run v2 Direct IAP service ${PROXY_SVC} in ${REGION} (SA=${RUNTIME_SA_EMAIL})..."
gcloud --quiet --project="$PROJECT" beta run deploy "$PROXY_SVC" \
  --region="$REGION" \
  --image="$IMAGE_URI" \
  --service-account="$RUNTIME_SA_EMAIL" \
  --port=8080 \
  --timeout=3600 \
  --cpu=1 --memory=512Mi \
  --min-instances=0 --max-instances=5 \
  --network="${NAME_PREFIX}-vpc" \
  --subnet="${NAME_PREFIX}-subnet" \
  --vpc-egress=private-ranges-only \
  --set-env-vars="UPSTREAM_HOST=${VM_INTERNAL_IP},UPSTREAM_PORT=8080" \
  --no-allow-unauthenticated \
  --iap

echo "→ Ensuring IAP service agent holds roles/run.invoker and binding IAP_USERS..."
gcloud --quiet --project="$PROJECT" beta services identity create --service=iap.googleapis.com >/dev/null 2>&1 || true
IAP_SA="service-${PROJECT_NUM}@gcp-sa-iap.iam.gserviceaccount.com"
gcloud --quiet --project="$PROJECT" run services add-iam-policy-binding "$PROXY_SVC" \
  --region="$REGION" \
  --member="serviceAccount:${IAP_SA}" \
  --role="roles/run.invoker" >/dev/null 2>&1 || true

IFS=',' read -ra USERS <<< "$IAP_USERS"
for u in "${USERS[@]}"; do
  u="$(echo "$u" | xargs)"
  [ -z "$u" ] && continue
  gcloud --quiet --project="$PROJECT" beta iap web add-iam-policy-binding \
    --resource-type=cloud-run \
    --region="$REGION" \
    --service="$PROXY_SVC" \
    --member="$u" \
    --role="roles/iap.httpsResourceAccessor" >/dev/null 2>&1 || true
  gcloud --quiet --project="$PROJECT" run services add-iam-policy-binding "$PROXY_SVC" \
    --region="$REGION" \
    --member="$u" \
    --role="roles/run.invoker" >/dev/null 2>&1 || true
done

SERVICE_URL=$(gcloud --quiet --project="$PROJECT" run services describe "$PROXY_SVC" \
  --region="$REGION" --format='value(status.url)')
echo
echo "✅ Cloud Run Direct IAP Ingress Ready (Zero Custom OAuth Client, Zero SSL Wait)."
echo "   Public URL : ${SERVICE_URL}/"
echo "   IAP Users  : ${IAP_USERS}"
echo "   Note       : Cloud Run streaming timeout is 3600s (use INGRESS_MODE=classic_lb for 86400s streams)."
