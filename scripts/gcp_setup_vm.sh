#!/usr/bin/env bash
# Optional: create a fresh Debian 12 VM sized for the hub, with a 100 GB
# data disk attached (formatted by scripts/install.sh at first run).
# Skip this if you already have a VM.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
if [ ! -f .env ]; then echo ".env missing"; exit 1; fi
set -a; . ./.env; set +a

: "${GOOGLE_CLOUD_PROJECT:?}"
: "${VM_NAME:?add to .env}"
: "${VM_ZONE:?add to .env}"

# Auto-detect actual VM zone if instance already exists in GCP
DETECTED_ZONE=$(gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute instances list --filter="name=$VM_NAME" --format="value(zone)" 2>/dev/null | head -n 1 || true)
if [ -n "$DETECTED_ZONE" ]; then
  VM_ZONE="$DETECTED_ZONE"
fi

VM_MACHINE_TYPE="${VM_MACHINE_TYPE:-n4-standard-2}"
DATA_DISK_GB="${DATA_DISK_GB:-100}"

REGION=$(echo "$VM_ZONE" | cut -d- -f1,2)
NAME_PREFIX="${NAME_PREFIX:-antigravity-web}"

echo "→ Ensuring all required Google Cloud APIs are enabled..."
gcloud --quiet --project=$GOOGLE_CLOUD_PROJECT services enable \
  compute.googleapis.com \
  iap.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com 2>/dev/null || true

echo "→ Ensuring VPC network, subnet, and Cloud NAT exist for Argolis compliance..."
gcloud --project=$GOOGLE_CLOUD_PROJECT compute networks create ${NAME_PREFIX}-vpc --subnet-mode=custom 2>/dev/null || true
gcloud --project=$GOOGLE_CLOUD_PROJECT compute networks subnets create ${NAME_PREFIX}-subnet --network=${NAME_PREFIX}-vpc --region=$REGION --range=10.0.1.0/24 2>/dev/null || true
gcloud --project=$GOOGLE_CLOUD_PROJECT compute routers create ${NAME_PREFIX}-router --network=${NAME_PREFIX}-vpc --region=$REGION 2>/dev/null || true
gcloud --project=$GOOGLE_CLOUD_PROJECT compute routers nats create ${NAME_PREFIX}-nat --router=${NAME_PREFIX}-router --region=$REGION --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges 2>/dev/null || true

echo "→ Creating VM $VM_NAME in $VM_ZONE ($VM_MACHINE_TYPE)…"
gcloud --project=$GOOGLE_CLOUD_PROJECT compute instances describe $VM_NAME --zone=$VM_ZONE 2>/dev/null && {
  echo "  VM already exists — skipping."
  exit 0
}
gcloud --project=$GOOGLE_CLOUD_PROJECT compute instances create $VM_NAME \
  --zone=$VM_ZONE \
  --machine-type=$VM_MACHINE_TYPE \
  --network=${NAME_PREFIX}-vpc \
  --subnet=${NAME_PREFIX}-subnet \
  --no-address \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=20GB --boot-disk-type=pd-balanced \
  --create-disk="name=${VM_NAME}-data,size=${DATA_DISK_GB}GB,type=pd-balanced,auto-delete=no" \
  --tags=${NAME_PREFIX} \
  --scopes=cloud-platform \
  --metadata=enable-oslogin=TRUE \
  --shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring 2>/dev/null || true

echo "→ Granting Vertex AI User role to Compute Engine default service account…"
PROJECT_NUM=$(gcloud projects describe $GOOGLE_CLOUD_PROJECT --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT --member="serviceAccount:${COMPUTE_SA}" --role="roles/aiplatform.user" --quiet 2>/dev/null || true

echo "  VM created. Wait ~30s for boot, then:"
echo "    gcloud compute ssh $VM_NAME --zone=$VM_ZONE --tunnel-through-iap"
echo "  and run scripts/install.sh."
