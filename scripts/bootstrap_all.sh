#!/usr/bin/env bash
# One-shot orchestrator: VM -> Ingress (Classic LB or Cloud Run Direct IAP) -> VM-side install.
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

ACTIVE_ACCT="$(gcloud config get-value account 2>/dev/null || true)"
export CLOUDSDK_CORE_ACCOUNT="${SSH_USER:-${GCP_ACCOUNT:-${ACTIVE_ACCT:?set GCP_ACCOUNT or run gcloud auth login}}}"
export IAP_USERS="${IAP_USERS:-user:${CLOUDSDK_CORE_ACCOUNT}}"
NAME_PREFIX="${NAME_PREFIX:-antigravity-web}"
INGRESS_MODE="${INGRESS_MODE:-classic_lb}"

# Auto-detect actual VM zone if instance already exists in GCP
DETECTED_ZONE=$(gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute instances list \
  --filter="name=$VM_NAME" --format="value(zone)" 2>/dev/null | head -n 1 || true)
if [ -n "$DETECTED_ZONE" ]; then
  VM_ZONE="$DETECTED_ZONE"
fi

ENABLE_KG="${ENABLE_KNOWLEDGE_GRAPH:-true}"
ENABLE_RESEARCH="${ENABLE_DEEP_RESEARCH:-true}"
ENABLE_WORKSPACE="${ENABLE_WORKSPACE_MCP:-true}"

echo "===== Antigravity Web Hub Module Setup ====="
echo "  [✓] Core Web Hub & Vertex AI Routing (Ingress: ${INGRESS_MODE})"
echo "  [$([ "$ENABLE_KG" = "true" ] && echo "✓" || echo " ")] Knowledge Graph Long-Term Memory (0ms cache & context injection)"
echo "  [$([ "$ENABLE_RESEARCH" = "true" ] && echo "✓" || echo " ")] On-Demand Deep Research FastMCP Server"
echo "  [$([ "$ENABLE_WORKSPACE" = "true" ] && echo "✓" || echo " ")] Native Google Workspace MCP Server"
echo "============================================"

echo "===== 1/3  Create VM (preflight zone + dedicated SA + skips if exists) ====="
"$HERE/gcp_setup_vm.sh"

# Re-source .env in case ACE-WS-05 zone preflight updated VM_ZONE
set -a; . ./.env; set +a
DETECTED_ZONE=$(gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute instances list \
  --filter="name=$VM_NAME" --format="value(zone)" 2>/dev/null | head -n 1 || true)
if [ -n "$DETECTED_ZONE" ]; then
  VM_ZONE="$DETECTED_ZONE"
fi
REGION="${VM_ZONE%-*}"

echo "===== 2/3  Provision Ingress (${INGRESS_MODE}) ====="
if [ "$INGRESS_MODE" = "cloud_run_direct_iap" ]; then
  "$HERE/gcp_setup_cloudrun_iap.sh"
else
  "$HERE/gcp_setup_lb.sh"
fi

gcloud_retry() {
  local retries=5
  local count=0
  until "$@"; do
    count=$((count + 1))
    if [ $count -ge $retries ]; then
      return 1
    fi
    echo "gcloud command failed — retrying ($count/$retries) in 5s..."
    sleep 5
  done
}

echo "===== 3/3  Install hub on VM (via SSH-over-IAP; verified CDN binaries on VM) ====="
REMOTE_DIR="/tmp/antigravity-web-hub"
TAR_FILE="/tmp/antigravity-hub-deploy.tar.gz"

echo "→ Packaging clean repository into $TAR_FILE..."
tar --exclude='.git' --exclude='venv' --exclude='node_modules' --exclude='bin' -czf "$TAR_FILE" -C "$REPO_ROOT" .

echo "→ Waiting for SSH-over-IAP readiness & transferring archive to VM ($VM_NAME in $VM_ZONE)..."
gcloud_retry gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute ssh "$VM_NAME" --zone="$VM_ZONE" --tunnel-through-iap \
  --ssh-flag="-o StrictHostKeyChecking=no" \
  --command="rm -rf $REMOTE_DIR && mkdir -p $REMOTE_DIR"

gcloud_retry gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute scp --tunnel-through-iap --zone="$VM_ZONE" \
  --scp-flag="-o StrictHostKeyChecking=no" \
  "$TAR_FILE" "$VM_NAME:/tmp/hub.tar.gz"

if [ "${TRANSFER_WORKSTATION_ADC:-false}" = "true" ] && [ -f "$HOME/.config/gcloud/application_default_credentials.json" ]; then
  echo "→ Transferring workstation Application Default Credentials (ADC) to VM..."
  gcloud_retry gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute ssh "$VM_NAME" --zone="$VM_ZONE" --tunnel-through-iap \
    --ssh-flag="-o StrictHostKeyChecking=no" \
    --command="mkdir -p ~/.config/gcloud"
  gcloud_retry gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute scp --tunnel-through-iap --zone="$VM_ZONE" \
    --scp-flag="-o StrictHostKeyChecking=no" \
    "$HOME/.config/gcloud/application_default_credentials.json" "$VM_NAME:~/.config/gcloud/application_default_credentials.json"
fi

echo "→ Unpacking archive & running verified installer on VM..."
gcloud_retry gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute ssh "$VM_NAME" --zone="$VM_ZONE" --tunnel-through-iap \
  --ssh-flag="-o StrictHostKeyChecking=no" \
  --command="tar -xzf /tmp/hub.tar.gz -C $REMOTE_DIR && cd $REMOTE_DIR && sudo -E bash scripts/install.sh"

echo
echo "===== DONE ====="
if [ "$INGRESS_MODE" = "cloud_run_direct_iap" ]; then
  PROXY_URL=$(gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" run services describe "${NAME_PREFIX}-proxy" --region="$REGION" --format='value(status.url)' 2>/dev/null || echo "")
  echo "Browse (Cloud Run Direct IAP): ${PROXY_URL}/"
else
  echo "Browse: https://$(gcloud --project="$GOOGLE_CLOUD_PROJECT" compute addresses describe "${NAME_PREFIX}-ip" --global --format='value(address)').nip.io/"
  echo "(Google-managed SSL cert takes up to ~15 min to provision on first setup.)"
fi
