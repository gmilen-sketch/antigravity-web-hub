#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# 🧹 [Antigravity Hub] Complete GCP Infrastructure Clean Destruction Script
# ==============================================================================
# Reads .env when present (or environment overrides) and removes ALL components
# provisioned for NAME_PREFIX / VM_NAME in reverse dependency order.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "${REPO_ROOT}/.env" ]; then
  set -a; . "${REPO_ROOT}/.env"; set +a
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
ACTIVE_ACCT="$(gcloud config get-value account 2>/dev/null || true)"
ACCOUNT="${GCP_ACCOUNT:-${SSH_USER:-${ACTIVE_ACCT:?set GCP_ACCOUNT}}}"
NAME_PREFIX="${NAME_PREFIX:-antigravity-web}"
VM_NAME="${VM_NAME:-antigravity-ge-hub}"
ZONE="${VM_ZONE:-${GCP_ZONE:-us-central1-c}}"
REGION="${GCP_REGION:-${ZONE%-*}}"

echo "============================================================"
echo "🧹 Destroying ALL Antigravity Hub components"
echo "   Project : $PROJECT_ID"
echo "   Prefix  : $NAME_PREFIX | VM: $VM_NAME ($ZONE)"
echo "============================================================"

# 1. Cloud Run Direct IAP Proxy & Artifact Registry (ACE-WS-04)
echo "==> [1/10] Deleting Cloud Run Direct IAP proxy & Artifact Registry..."
gcloud compute instances list --project="$PROJECT_ID" --account="$ACCOUNT" --filter="name=${VM_NAME}" --format="value(zone)" 2>/dev/null | head -n 1 | while read -r dz; do
  [ -n "$dz" ] && echo "  Detected VM zone: $dz"
done || true
# Detach Direct VPC Egress before deleting the Cloud Run service to accelerate serverless IP release
if gcloud run services describe "${NAME_PREFIX}-proxy" --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" >/dev/null 2>&1; then
  gcloud run services update "${NAME_PREFIX}-proxy" --clear-network --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet >/dev/null 2>&1 || true
  gcloud run services delete "${NAME_PREFIX}-proxy" --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
fi
gcloud artifacts repositories delete "${NAME_PREFIX}-proxy-repo" --location="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 2. Forwarding Rules
echo "==> [2/10] Deleting Forwarding Rules..."
gcloud compute forwarding-rules delete "${NAME_PREFIX}-fr" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute forwarding-rules delete "${NAME_PREFIX}-http-fr" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 3. Target Proxies & URL Maps
echo "==> [3/10] Deleting Target Proxies & URL Maps..."
gcloud compute target-https-proxies delete "${NAME_PREFIX}-tp" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute target-http-proxies delete "${NAME_PREFIX}-http-proxy" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute url-maps delete "${NAME_PREFIX}-um" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute url-maps delete "${NAME_PREFIX}-http-redirect-um" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 4. Backend Service & Health Check
echo "==> [4/10] Deleting Backend Service & Health Check..."
gcloud compute backend-services delete "${NAME_PREFIX}-bs" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute health-checks delete "${NAME_PREFIX}-hc" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 5. Instance Group, VM, Data Disk & Idle Schedule (ACE-WS-06)
echo "==> [5/10] Deleting Instance Group, VM Instance, Data Disk & Schedule..."
gcloud compute instance-groups unmanaged delete "${NAME_PREFIX}-ig" --zone="$ZONE" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute instances remove-resource-policies "$VM_NAME" --zone="$ZONE" --resource-policies="${NAME_PREFIX}-idle-schedule" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute instances delete "$VM_NAME" --zone="$ZONE" --delete-disks=all --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute disks delete "${VM_NAME}-data" --zone="$ZONE" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute resource-policies delete "${NAME_PREFIX}-idle-schedule" --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 6. Static IPs & Managed SSL Certs
echo "==> [6/10] Releasing Static IP & Managed SSL Certificates..."
gcloud compute addresses delete "${NAME_PREFIX}-ip" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
(gcloud compute ssl-certificates list --project="$PROJECT_ID" --account="$ACCOUNT" --format="value(name)" 2>/dev/null | grep "^${NAME_PREFIX}-cert" || true) | while read -r cert; do
  [ -n "$cert" ] && gcloud compute ssl-certificates delete "$cert" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
done

# 7. FQDN Network Firewall Policy (ACE-WS-02)
echo "==> [7/10] Deleting FQDN Egress Network Firewall Policy..."
EGRESS_POLICY="${NAME_PREFIX}-egress-policy"
gcloud compute network-firewall-policies associations delete --firewall-policy="$EGRESS_POLICY" --global-firewall-policy --name="${EGRESS_POLICY}-assoc" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute network-firewall-policies delete "$EGRESS_POLICY" --global --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

# 8. Private Google Access DNS Zone (ACE-WS-02)
echo "==> [8/10] Deleting Private Google Access DNS Zone..."
PGA_ZONE="${NAME_PREFIX}-pga-googleapis"
if gcloud dns managed-zones describe "$PGA_ZONE" --project="$PROJECT_ID" --account="$ACCOUNT" >/dev/null 2>&1; then
  gcloud dns record-sets delete "private.googleapis.com." --zone="$PGA_ZONE" --type=A --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
  gcloud dns record-sets delete "*.googleapis.com." --zone="$PGA_ZONE" --type=CNAME --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
  gcloud dns managed-zones delete "$PGA_ZONE" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
fi

# 9. VPC Firewall Rules, Cloud NAT, Router, Subnet & Custom VPC
echo "==> [9/10] Deleting VPC Firewall Rules, NAT, Router, Subnet & VPC..."
(gcloud compute firewall-rules list --project="$PROJECT_ID" --account="$ACCOUNT" --filter="network~/${NAME_PREFIX}-vpc$" --format="value(name)" 2>/dev/null || true) | while read -r fw; do
  [ -n "$fw" ] && gcloud compute firewall-rules delete "$fw" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
done
gcloud compute routers nats delete "${NAME_PREFIX}-nat" --router="${NAME_PREFIX}-router" --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
gcloud compute routers delete "${NAME_PREFIX}-router" --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true
# Cloud Run Direct VPC Egress holds a serverless-ipv4-cloudrun-* reservation for up to ~20 min after delete
SUBNET_DELETED="true"
for _attempt in $(seq 1 4); do
  if ! gcloud compute networks subnets describe "${NAME_PREFIX}-subnet" --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" >/dev/null 2>&1; then
    break
  fi
  if gcloud compute networks subnets delete "${NAME_PREFIX}-subnet" --region="$REGION" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null; then
    break
  fi
  if [ "$_attempt" -eq 4 ]; then
    SUBNET_DELETED="false"
    echo "  ⚠ Subnet ${NAME_PREFIX}-subnet still held by GCP Cloud Run Direct VPC Egress serverless-ipv4 cooldown (~15-20m); re-run gcp_destroy.sh after cooldown."
  else
    sleep 10
  fi
done
if [ "$SUBNET_DELETED" = "true" ]; then
  for _attempt in $(seq 1 3); do
    if ! gcloud compute networks describe "${NAME_PREFIX}-vpc" --project="$PROJECT_ID" --account="$ACCOUNT" >/dev/null 2>&1; then
      break
    fi
    gcloud compute networks delete "${NAME_PREFIX}-vpc" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null && break || sleep 5
  done
fi

# 10. Dedicated Runtime Service Account & Project IAM Bindings (ACE-WS-02)
echo "==> [10/10] Deleting Dedicated Runtime Service Account & IAM Bindings..."
RUNTIME_SA_EMAIL="${NAME_PREFIX}-runtime@${PROJECT_ID}.iam.gserviceaccount.com"
for role in roles/aiplatform.user roles/logging.logWriter roles/monitoring.metricWriter roles/bigquery.jobUser; do
  gcloud projects remove-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:${RUNTIME_SA_EMAIL}" --role="$role" --account="$ACCOUNT" --quiet >/dev/null 2>&1 || true
done
gcloud iam service-accounts delete "$RUNTIME_SA_EMAIL" --project="$PROJECT_ID" --account="$ACCOUNT" --quiet 2>/dev/null || true

echo "============================================================"
echo "✅ All '${NAME_PREFIX}' Antigravity Hub components destroyed."
echo "============================================================"
