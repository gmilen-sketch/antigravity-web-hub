#!/bin/bash
# ==============================================================================
# Antigravity Web Hub - Clean-Room Destroy, Deploy & E2E Verification Pipeline
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-second-test-project-393510}"
ZONE="${VM_ZONE:-us-central1-c}"
VM_NAME="${VM_NAME:-antigravity-ge-hub}"
SSH_USER="${SSH_USER:-admin@mgenchev.altostrat.com}"
LB_IP="${LB_IP:-34.160.89.22}"

echo "============================================================"
echo "🚀 [Antigravity Hub] Standalone Clean-Room Deploy & Verify"
echo "Target Project: ${PROJECT_ID} | VM: ${VM_NAME} (${ZONE})"
echo "============================================================"

# Step 1: Package clean repository
TAR_ARCHIVE="/tmp/antigravity-hub-deploy.tar.gz"
echo "📦 [1/4] Packaging clean repository into ${TAR_ARCHIVE}..."
rm -f "${TAR_ARCHIVE}"
tar --exclude='.git' --exclude='venv' --exclude='node_modules' -czf "${TAR_ARCHIVE}" -C "${REPO_ROOT}" .

# Step 2: Transfer package and run clean-room destroy & installer
echo "🚚 [2/4] Uploading deployment package and runner to ${VM_NAME}..."
gcloud compute scp "${TAR_ARCHIVE}" "${VM_NAME}:/tmp/hub.tar.gz" \
  --zone="${ZONE}" \
  --project="${PROJECT_ID}" \
  --account="${SSH_USER}" \
  --tunnel-through-iap \
  --scp-flag="-o StrictHostKeyChecking=no"

gcloud compute scp "${SCRIPT_DIR}/remote_runner.sh" "${VM_NAME}:/tmp/remote_runner.sh" \
  --zone="${ZONE}" \
  --project="${PROJECT_ID}" \
  --account="${SSH_USER}" \
  --tunnel-through-iap \
  --scp-flag="-o StrictHostKeyChecking=no"

echo "⚙️  [3/4] Executing remote clean-room destroy & installation on ${VM_NAME}..."
gcloud compute ssh "${VM_NAME}" \
  --zone="${ZONE}" \
  --project="${PROJECT_ID}" \
  --account="${SSH_USER}" \
  --tunnel-through-iap \
  --ssh-flag="-o StrictHostKeyChecking=no" \
  --command="bash /tmp/remote_runner.sh"

echo "✅ Remote deployment completed successfully."

# Step 3: Automated End-to-End Verification via Headless Chrome CDP
echo "🧪 [4/4] Polling Load Balancer Health Check & Running E2E Automated Verification..."

# Wait for LB health check to confirm 200 OK or 302 (IAP OAuth redirect)
for i in {1..15}; do
  status_code=$(curl -s -o /dev/null -w "%{http_code}" "http://${LB_IP}/" || echo "000")
  if [ "$status_code" = "200" ] || [ "$status_code" = "302" ]; then
    echo "Load Balancer is healthy (HTTP ${status_code} after ${i} checks)."
    break
  fi
  echo "Waiting for Load Balancer health check convergence (status: ${status_code}, attempt ${i}/15)..."
  sleep 2
done

# Step 4: Open background IAP port-forward for Chrome CDP verification
LOCAL_PORT=18080
pkill -f "18080:localhost:8080" 2>/dev/null || true
gcloud compute ssh "${VM_NAME}" \
  --zone="${ZONE}" \
  --project="${PROJECT_ID}" \
  --account="${SSH_USER}" \
  --tunnel-through-iap \
  --ssh-flag="-o StrictHostKeyChecking=no" \
  --ssh-flag="-L ${LOCAL_PORT}:localhost:8080" \
  --ssh-flag="-N" &
TUNNEL_PID=$!
sleep 4

cleanup_tunnel() {
  kill -TERM "$TUNNEL_PID" 2>/dev/null || true
}
trap cleanup_tunnel EXIT

# Step 5: Run Node.js CDP verification against local tunnel endpoint
export LB_IP="127.0.0.1:${LOCAL_PORT}"
node "${SCRIPT_DIR}/verify_e2e.js"


