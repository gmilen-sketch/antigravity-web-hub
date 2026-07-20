#!/usr/bin/env bash
# One-shot orchestrator: VM → LB → IAP → VM-side install.
# Requires .env and `gcloud auth login` on the workstation running this.
# Idempotent — safe to re-run any stage.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$HERE/.." && pwd)
cd "$REPO_ROOT"
if [ ! -f .env ]; then echo ".env missing — copy .env.example first"; exit 1; fi
set -a; . ./.env; set +a
: "${GOOGLE_CLOUD_PROJECT:?}"
: "${VM_NAME:?}"
: "${VM_ZONE:?}"

echo "===== 1/3  Create VM (skips if exists) ====="
"$HERE/gcp_setup_vm.sh"

echo "===== 2/3  Provision LB + IAP ====="
"$HERE/gcp_setup_lb.sh"

echo "===== 3/3  Install hub on VM (via SSH-over-IAP) ====="
# Rsync repo tree up, then run install.sh remotely.
REMOTE_DIR="/tmp/antigravity-web-hub"
gcloud --project=$GOOGLE_CLOUD_PROJECT compute ssh $VM_NAME --zone=$VM_ZONE --tunnel-through-iap \
  --command="mkdir -p $REMOTE_DIR"
gcloud --project=$GOOGLE_CLOUD_PROJECT compute scp --recurse --tunnel-through-iap --zone=$VM_ZONE \
  ./ $VM_NAME:$REMOTE_DIR/
gcloud --project=$GOOGLE_CLOUD_PROJECT compute ssh $VM_NAME --zone=$VM_ZONE --tunnel-through-iap \
  --command="cd $REMOTE_DIR && sudo -E bash scripts/install.sh"

echo
echo "===== DONE ====="
echo "Browse: https://$(gcloud --project=$GOOGLE_CLOUD_PROJECT compute addresses describe antigravity-web-ip --global --format='value(address)').nip.io/"
echo "(Google-managed SSL cert takes up to ~15 min to provision on first setup.)"
