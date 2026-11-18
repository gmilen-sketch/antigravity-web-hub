#!/usr/bin/env bash
# Provisions a hardened Debian 12 GCE VM for Antigravity Web Hub with:
#   - ACE-WS-05: Multi-zone CPU quota & machine-type preflight with auto-fallback
#   - ACE-WS-02: Dedicated least-privilege runtime SA, subnet PGA, lateral deny, PGA DNS, opt-in FQDN egress
#   - ACE-WS-06: Opt-in GCE Instance Schedule cost governance
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
if [ ! -f .env ]; then echo ".env missing"; exit 1; fi
set -a; . ./.env; set +a

: "${GOOGLE_CLOUD_PROJECT:?}"
: "${VM_NAME:?add to .env}"
: "${VM_ZONE:?add to .env}"

ACTIVE_ACCT="$(gcloud config get-value account 2>/dev/null || true)"
export CLOUDSDK_CORE_ACCOUNT="${SSH_USER:-${GCP_ACCOUNT:-${ACTIVE_ACCT:-admin@example-enterprise.com}}}"

# Auto-detect actual VM zone if instance already exists in GCP
DETECTED_ZONE=$(gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute instances list \
  --filter="name=$VM_NAME" --format="value(zone)" 2>/dev/null | head -n 1 || true)
if [ -n "$DETECTED_ZONE" ]; then
  VM_ZONE="$DETECTED_ZONE"
fi

VM_MACHINE_TYPE="${VM_MACHINE_TYPE:-n4-standard-2}"
DATA_DISK_GB="${DATA_DISK_GB:-100}"
NAME_PREFIX="${NAME_PREFIX:-antigravity-web}"
ENABLE_ZONE_PREFLIGHT="${ENABLE_ZONE_PREFLIGHT:-true}"
ENABLE_PGA_DNS="${ENABLE_PGA_DNS:-true}"
ENABLE_FQDN_EGRESS_POLICY="${ENABLE_FQDN_EGRESS_POLICY:-false}"
ENABLE_IDLE_SCHEDULE="${ENABLE_IDLE_SCHEDULE:-false}"
IDLE_STOP_CRON="${IDLE_STOP_CRON:-0 22 * * *}"
IDLE_SCHEDULE_TZ="${IDLE_SCHEDULE_TZ:-UTC}"

echo "→ Ensuring all required Google Cloud APIs are enabled..."
gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" services enable \
  compute.googleapis.com \
  iap.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  dns.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com 2>/dev/null || true

# ACE-WS-05: Multi-zone capacity & quota preflight before provisioning
if [ -z "$DETECTED_ZONE" ] && [ "$ENABLE_ZONE_PREFLIGHT" = "true" ] && [ -f "$REPO_ROOT/scripts/preflight_zone_check.py" ]; then
  echo "→ Running multi-zone capacity & CPU quota preflight (preferred=${VM_ZONE}, type=${VM_MACHINE_TYPE})..."
  PREFLIGHT_ARGS=(
    --project "$GOOGLE_CLOUD_PROJECT"
    --machine-type "$VM_MACHINE_TYPE"
    --preferred-zone "$VM_ZONE"
    --account "$CLOUDSDK_CORE_ACCOUNT"
  )
  if [ -n "${FALLBACK_ZONES:-}" ]; then
    PREFLIGHT_ARGS+=(--fallback-zones "$FALLBACK_ZONES")
  fi
  if RESOLVED_ZONE=$(python3 -B "$REPO_ROOT/scripts/preflight_zone_check.py" "${PREFLIGHT_ARGS[@]}" 2>/dev/null) && [ -n "$RESOLVED_ZONE" ]; then
    if [ "$RESOLVED_ZONE" != "$VM_ZONE" ]; then
      echo "  ⚠ Preferred zone ${VM_ZONE} unavailable/over-quota; failing over to ${RESOLVED_ZONE}."
      VM_ZONE="$RESOLVED_ZONE"
      if grep -q "^VM_ZONE=" .env 2>/dev/null; then
        sed -i "s/^VM_ZONE=.*/VM_ZONE=${VM_ZONE}/g" .env
      fi
    else
      echo "  ✓ Preflight confirmed stock & quota in ${VM_ZONE}."
    fi
  else
    echo "  ⚠ Zone preflight API check skipped/unavailable; proceeding with ${VM_ZONE}."
  fi
fi

REGION="${VM_ZONE%-*}"

# ACE-WS-02: Dedicated least-privilege runtime Service Account (never default Compute SA)
RUNTIME_SA_ID="${NAME_PREFIX}-runtime"
RUNTIME_SA_EMAIL="${RUNTIME_SA_ID}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
echo "→ Ensuring dedicated least-privilege runtime Service Account (${RUNTIME_SA_EMAIL})..."
if ! gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" iam service-accounts describe "$RUNTIME_SA_EMAIL" >/dev/null 2>&1; then
  gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" iam service-accounts create "$RUNTIME_SA_ID" \
    --display-name="Antigravity Web Hub Runtime SA (${NAME_PREFIX})"
  sleep 5
fi
for role in roles/aiplatform.user roles/logging.logWriter roles/monitoring.metricWriter roles/bigquery.jobUser; do
  gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:${RUNTIME_SA_EMAIL}" --role="$role" >/dev/null 2>&1 || true
done

echo "→ Ensuring custom VPC, PGA-enabled subnet, Cloud NAT, and lateral-deny firewall..."
gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute networks create "${NAME_PREFIX}-vpc" \
  --subnet-mode=custom 2>/dev/null || true
gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute networks subnets create "${NAME_PREFIX}-subnet" \
  --network="${NAME_PREFIX}-vpc" --region="$REGION" --range=10.0.1.0/24 \
  --enable-private-ip-google-access 2>/dev/null || \
  gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute networks subnets update "${NAME_PREFIX}-subnet" \
    --region="$REGION" --enable-private-ip-google-access 2>/dev/null || true
gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute routers create "${NAME_PREFIX}-router" \
  --network="${NAME_PREFIX}-vpc" --region="$REGION" 2>/dev/null || true
gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute routers nats create "${NAME_PREFIX}-nat" \
  --router="${NAME_PREFIX}-router" --region="$REGION" \
  --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges 2>/dev/null || true

# Deny unexpected lateral VM-to-VM traffic inside subnet (priority 1000; explicit proxy rule uses 900)
gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute firewall-rules create "${NAME_PREFIX}-deny-lateral" \
  --network="${NAME_PREFIX}-vpc" --direction=INGRESS --action=DENY --rules=all \
  --source-ranges=10.0.1.0/24 --priority=1000 2>/dev/null || true

# Allow IAP SSH tunneling (35.235.240.0/20 -> tcp:22)
gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute firewall-rules create "${NAME_PREFIX}-allow-iap" \
  --network="${NAME_PREFIX}-vpc" --direction=INGRESS --action=allow --rules=tcp:22 \
  --source-ranges=35.235.240.0/20 --target-tags="${NAME_PREFIX}" --priority=900 2>/dev/null || true

# ACE-WS-02: Private Google Access private DNS zone (199.36.153.8/30)
if [ "$ENABLE_PGA_DNS" = "true" ]; then
  PGA_ZONE="${NAME_PREFIX}-pga-googleapis"
  echo "→ Ensuring Private Google Access DNS zone (${PGA_ZONE} -> 199.36.153.8/30)..."
  if ! gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" dns managed-zones describe "$PGA_ZONE" >/dev/null 2>&1; then
    gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" dns managed-zones create "$PGA_ZONE" \
      --dns-name="googleapis.com." --visibility=private --networks="${NAME_PREFIX}-vpc" \
      --description="Private Google Access routing for ${NAME_PREFIX}"
    gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" dns record-sets create "private.googleapis.com." \
      --zone="$PGA_ZONE" --type=A --ttl=300 --rrdatas="199.36.153.8,199.36.153.9,199.36.153.10,199.36.153.11"
    gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" dns record-sets create "*.googleapis.com." \
      --zone="$PGA_ZONE" --type=CNAME --ttl=300 --rrdatas="private.googleapis.com."
  fi
fi

# ACE-WS-02: Opt-in FQDN Egress Firewall Policy (default-deny priority 65000 + allowlist)
if [ "$ENABLE_FQDN_EGRESS_POLICY" = "true" ]; then
  EGRESS_POLICY="${NAME_PREFIX}-egress-policy"
  DEFAULT_FQDNS="aiplatform.googleapis.com,storage.googleapis.com,packages.cloud.google.com,dl.google.com,antigravity.google,antigravity.static.usercontent.goog,antigravity-hub-auto-updater-974169037036.us-central1.run.app,antigravity-cli-auto-updater-974169037036.us-central1.run.app,deb.debian.org,security.debian.org,cdn-fastly.deb.debian.org,pypi.org,files.pythonhosted.org,registry.npmjs.org,github.com,api.github.com,objects.githubusercontent.com,raw.githubusercontent.com"
  ALLOW_FQDNS="${EGRESS_FQDN_ALLOWLIST:-$DEFAULT_FQDNS}"
  echo "→ Ensuring FQDN egress allowlist policy (${EGRESS_POLICY})..."
  if ! gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute network-firewall-policies describe "$EGRESS_POLICY" --global >/dev/null 2>&1; then
    gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute network-firewall-policies create "$EGRESS_POLICY" \
      --global --description="FQDN egress allowlist for ${NAME_PREFIX}"
    gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute network-firewall-policies rules create 1000 \
      --firewall-policy="$EGRESS_POLICY" --global-firewall-policy --direction=EGRESS \
      --target-service-accounts="$RUNTIME_SA_EMAIL" --action=allow --layer4-configs=tcp:443 \
      --dest-ip-ranges=199.36.153.8/30 --enable-logging --description="Allow Private Google Access"
    gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute network-firewall-policies rules create 1100 \
      --firewall-policy="$EGRESS_POLICY" --global-firewall-policy --direction=EGRESS \
      --target-service-accounts="$RUNTIME_SA_EMAIL" --action=allow --layer4-configs=tcp:443,tcp:80 \
      --dest-fqdns="$ALLOW_FQDNS" --enable-logging --description="Allowlisted external FQDNs"
    gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute network-firewall-policies rules create 65000 \
      --firewall-policy="$EGRESS_POLICY" --global-firewall-policy --direction=EGRESS \
      --target-service-accounts="$RUNTIME_SA_EMAIL" --action=deny --layer4-configs=all \
      --dest-ip-ranges=0.0.0.0/0 --enable-logging --description="Default deny egress"
    gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute network-firewall-policies associations create \
      --firewall-policy="$EGRESS_POLICY" --global-firewall-policy --network="${NAME_PREFIX}-vpc" \
      --name="${EGRESS_POLICY}-assoc"
  fi
fi

echo "→ Creating Shielded VM $VM_NAME in $VM_ZONE ($VM_MACHINE_TYPE, SA=${RUNTIME_SA_EMAIL})..."
if gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute instances describe "$VM_NAME" --zone="$VM_ZONE" >/dev/null 2>&1; then
  echo "  VM already exists — skipping creation."
else
  DISK_TYPE="pd-balanced"
  if [[ "$VM_MACHINE_TYPE" == n4* || "$VM_MACHINE_TYPE" == c3* || "$VM_MACHINE_TYPE" == c4* ]]; then
    DISK_TYPE="hyperdisk-balanced"
  fi
  gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute instances create "$VM_NAME" \
    --zone="$VM_ZONE" \
    --machine-type="$VM_MACHINE_TYPE" \
    --network="${NAME_PREFIX}-vpc" \
    --subnet="${NAME_PREFIX}-subnet" \
    --no-address \
    --service-account="$RUNTIME_SA_EMAIL" \
    --image-family=debian-12 --image-project=debian-cloud \
    --boot-disk-size=20GB --boot-disk-type="$DISK_TYPE" \
    --create-disk="name=${VM_NAME}-data,size=${DATA_DISK_GB}GB,type=${DISK_TYPE},auto-delete=no" \
    --tags="${NAME_PREFIX}" \
    --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/userinfo.profile,openid \
    --metadata=enable-oslogin=TRUE \
    --shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring
fi

# ACE-WS-06: Opt-in GCE Instance Schedule cost governance
if [ "$ENABLE_IDLE_SCHEDULE" = "true" ]; then
  SCHED_NAME="${NAME_PREFIX}-idle-schedule"
  echo "→ Attaching GCE auto-stop instance schedule (${SCHED_NAME}: '${IDLE_STOP_CRON}' ${IDLE_SCHEDULE_TZ})..."
  PROJECT_NUM=$(gcloud --quiet projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')
  GCE_AGENT="service-${PROJECT_NUM}@compute-system.iam.gserviceaccount.com"
  gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
    --member="serviceAccount:${GCE_AGENT}" --role="roles/compute.instanceAdmin.v1" >/dev/null 2>&1 || true
  if ! gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute resource-policies describe "$SCHED_NAME" --region="$REGION" >/dev/null 2>&1; then
    gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute resource-policies create instance-schedule "$SCHED_NAME" \
      --region="$REGION" \
      --vm-stop-schedule="$IDLE_STOP_CRON" \
      --timezone="$IDLE_SCHEDULE_TZ" \
      --description="Automated off-hours stop schedule for ${NAME_PREFIX}"
  fi
  gcloud --quiet --project="$GOOGLE_CLOUD_PROJECT" compute instances add-resource-policies "$VM_NAME" \
    --zone="$VM_ZONE" --resource-policies="$SCHED_NAME" 2>/dev/null || true
fi

echo "  VM ${VM_NAME} ready in ${VM_ZONE} with dedicated SA ${RUNTIME_SA_EMAIL}."
