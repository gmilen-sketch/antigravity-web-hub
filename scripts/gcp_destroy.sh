#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# 🧹 [Antigravity Hub] GCP Infrastructure Clean Destruction Script
# ==============================================================================

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-second-test-project-393510}"
ACCOUNT="${GCP_ACCOUNT:-admin@mgenchev.altostrat.com}"
ZONE="${GCP_ZONE:-us-central1-c}"
REGION="${GCP_REGION:-us-central1}"

echo "============================================================"
echo "🧹 Destroying all Antigravity Hub infrastructure in project: $PROJECT_ID"
echo "============================================================"

# 1. Forwarding Rules
echo "==> [1/8] Deleting Forwarding Rules..."
gcloud compute forwarding-rules delete antigravity-web-fr --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute forwarding-rules delete antigravity-web-http-fr --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute forwarding-rules delete antigravity-nlb-rule --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 2. Target Proxies
echo "==> [2/8] Deleting Target Proxies..."
gcloud compute target-https-proxies delete antigravity-web-tp --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute target-http-proxies delete antigravity-web-http-proxy --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute target-pools delete antigravity-tp --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 3. URL Map
echo "==> [3/8] Deleting URL Map..."
gcloud compute url-maps delete antigravity-web-um --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 4. Backend Service
echo "==> [4/8] Deleting Backend Service..."
gcloud compute backend-services delete antigravity-web-bs --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 5. Health Check
echo "==> [5/8] Deleting Health Check..."
gcloud compute health-checks delete antigravity-web-hc --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute http-health-checks delete antigravity-nlb-hc --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 6. Instance Group & VM Instance
echo "==> [6/8] Deleting Instance Group & VM Instance..."
gcloud compute instance-groups unmanaged delete antigravity-web-ig --zone="$ZONE" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute instances delete antigravity-ge-hub --zone="$ZONE" --project="$PROJECT_ID" --account="$ACCOUNT" --delete-disks=all --quiet 2>/dev/null || true

# 7. Static IP Addresses
echo "==> [7/8] Releasing Static External IP Addresses..."
gcloud compute addresses delete antigravity-web-ip --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute addresses delete antigravity-nlb-ip --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 8. Firewall Rules & SSL Certs
echo "==> [8/8] Deleting Firewall Rules & SSL Certificates..."
gcloud compute firewall-rules delete allow-antigravity-web-secondproject --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute ssl-certificates list --project="$PROJECT_ID" --account="$ACCOUNT" --format="value(name)" 2>/dev/null | grep "antigravity" | while read -r cert; do
  gcloud compute ssl-certificates delete "$cert" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
done

echo "============================================================"
echo "✅ All Antigravity Hub resources successfully destroyed."
echo "============================================================"
