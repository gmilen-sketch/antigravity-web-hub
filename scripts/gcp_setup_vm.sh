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
VM_MACHINE_TYPE="${VM_MACHINE_TYPE:-e2-standard-2}"
DATA_DISK_GB="${DATA_DISK_GB:-100}"

echo "→ Creating VM $VM_NAME in $VM_ZONE ($VM_MACHINE_TYPE)…"
gcloud --project=$GOOGLE_CLOUD_PROJECT compute instances describe $VM_NAME --zone=$VM_ZONE 2>/dev/null && {
  echo "  VM already exists — skipping."
  exit 0
}
gcloud --project=$GOOGLE_CLOUD_PROJECT compute instances create $VM_NAME \
  --zone=$VM_ZONE \
  --machine-type=$VM_MACHINE_TYPE \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=20GB --boot-disk-type=pd-balanced \
  --create-disk="name=${VM_NAME}-data,size=${DATA_DISK_GB}GB,type=pd-balanced,auto-delete=no" \
  --tags=antigravity-web \
  --scopes=cloud-platform \
  --metadata=enable-oslogin=TRUE \
  --shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring

echo "  VM created. Wait ~30s for boot, then:"
echo "    gcloud compute ssh $VM_NAME --zone=$VM_ZONE --tunnel-through-iap"
echo "  and run scripts/install.sh."
