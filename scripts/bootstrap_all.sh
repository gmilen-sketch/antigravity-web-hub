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

gcloud_retry() {
  local retries=5
  local count=0
  until "$@"; do
    count=$((count + 1))
    if [ $count -ge $retries ]; then
      return 1
    fi
    echo "gcloud command failed — retrying ($count/$retries) in 3s..."
    pkill -9 -f "gcloud" 2>/dev/null || true
    pkill -9 -f "ecp" 2>/dev/null || true
    sleep 3
  done
}

echo "===== 3/3  Install hub on VM (via SSH-over-IAP) ====="
REMOTE_DIR="/tmp/antigravity-web-hub"
TAR_FILE="/tmp/antigravity-hub-deploy.tar.gz"

# Ensure language_server binary is packaged from local workstation if not present in repo bin/
if [ ! -f "$REPO_ROOT/bin/language_server" ]; then
  LOCAL_SERVER=""
  if [ -f "$HOME/.gemini/antigravity/bin/language_server" ]; then
    LOCAL_SERVER="$HOME/.gemini/antigravity/bin/language_server"
  elif [ -f "/usr/local/google/home/$USER/.gemini/antigravity/bin/language_server" ]; then
    LOCAL_SERVER="/usr/local/google/home/$USER/.gemini/antigravity/bin/language_server"
  fi
  if [ -n "$LOCAL_SERVER" ]; then
    echo "→ Found local language_server binary at $LOCAL_SERVER — copying into deployment package..."
    mkdir -p "$REPO_ROOT/bin"
    cp "$LOCAL_SERVER" "$REPO_ROOT/bin/language_server"
    chmod 0755 "$REPO_ROOT/bin/language_server"
  fi
fi

echo "→ Packaging repository into $TAR_FILE..."
tar --exclude='.git' --exclude='venv' --exclude='node_modules' -czf "$TAR_FILE" -C "$REPO_ROOT" .


echo "→ Transferring archive to VM..."
gcloud_retry gcloud --quiet --project=$GOOGLE_CLOUD_PROJECT compute ssh $VM_NAME --zone=$VM_ZONE --tunnel-through-iap \
  --command="rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR"

gcloud_retry gcloud --quiet --project=$GOOGLE_CLOUD_PROJECT compute scp --tunnel-through-iap --zone=$VM_ZONE \
  "$TAR_FILE" "$VM_NAME:/tmp/hub.tar.gz"

echo "→ Unpacking archive & running installer on VM..."
gcloud_retry gcloud --quiet --project=$GOOGLE_CLOUD_PROJECT compute ssh $VM_NAME --zone=$VM_ZONE --tunnel-through-iap \
  --command="tar -xzf /tmp/hub.tar.gz -C $REMOTE_DIR && cd $REMOTE_DIR && sudo -E bash scripts/install.sh"

echo
echo "===== DONE ====="
echo "Browse: https://$(gcloud --project=$GOOGLE_CLOUD_PROJECT compute addresses describe antigravity-web-ip --global --format='value(address)').nip.io/"
echo "(Google-managed SSL cert takes up to ~15 min to provision on first setup.)"
