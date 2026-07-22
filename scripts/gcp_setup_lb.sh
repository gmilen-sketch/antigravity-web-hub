#!/usr/bin/env bash
# Provision a GCP Classic HTTPS Load Balancer + IAP fronting a jumpstation VM.
# Idempotent — safe to re-run. Reads .env from repo root.
#
# What it creates (in order):
#   1. Reserved global static IPv4         → antigravity-web-ip
#   2. Firewall rules                      → antigravity-web-allow-lb, ...-allow-iap
#   3. Instance group (unmanaged)          → antigravity-web-ig  (adds your VM)
#   4. Health check                        → antigravity-web-hc  (TCP :8080)
#   5. Backend service                     → antigravity-web-bs  (timeout 86400)
#   6. Google-managed SSL cert             → antigravity-web-cert  (for <ip>.nip.io)
#   7. URL map                             → antigravity-web-um
#   8. Target HTTPS proxy                  → antigravity-web-tp
#   9. Global forwarding rule              → antigravity-web-fr  (:443)
#  10. Enable IAP on the backend service
#  11. Grants IAM: IAP_USERS from .env  → roles/iap.httpsResourceAccessor
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
if [ ! -f .env ]; then echo ".env missing — copy .env.example first" >&2; exit 1; fi
set -a; . ./.env; set +a

: "${GOOGLE_CLOUD_PROJECT:?set in .env}"
: "${VM_NAME:?add to .env — the jumpstation VM name}"
: "${VM_ZONE:?add to .env — e.g. us-central1-a}"
: "${IAP_USERS:?add to .env — comma-separated list of user:you@example.com,group:eng@…}"

NAME_PREFIX="${NAME_PREFIX:-antigravity-web}"
PROJECT=$GOOGLE_CLOUD_PROJECT

echo "→ Ensuring all required Google Cloud APIs are enabled..."
gcloud --quiet --project=$PROJECT services enable \
  compute.googleapis.com \
  iap.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com \
  serviceusage.googleapis.com 2>/dev/null || true

gcloud_retry() {
  local retries=5
  local count=0
  until "$@"; do
    count=$((count + 1))
    if [ $count -ge $retries ]; then
      return 1
    fi
    pkill -f "gcloud" 2>/dev/null || true
    sleep 2
  done
}

echo "→ Reserving static IP…"
gcloud --project=$PROJECT compute addresses create ${NAME_PREFIX}-ip --global --ip-version=IPV4 2>/dev/null || true
IP=$(gcloud_retry gcloud --project=$PROJECT compute addresses describe ${NAME_PREFIX}-ip --global --format='value(address)')

# If PUBLIC_DOMAIN is set in .env, use that (real domain, no cert warnings once
# a Google-managed cert is issued for it). Otherwise fall back to <ip>.nip.io.
if [ -n "${PUBLIC_DOMAIN:-}" ]; then
  HOST="$PUBLIC_DOMAIN"
  echo "  reserved IP=$IP  hostname=$HOST (custom domain)"
  echo
  echo "  ⚠  BEFORE THIS CAN VALIDATE: add a DNS A record"
  echo "     $HOST.  A  $IP"
  echo "     in whatever DNS you use for the parent zone."
  echo "     Google-managed cert provisioning will loop until the A record resolves."
  echo
else
  HOST="${IP}.nip.io"
  echo "  reserved IP=$IP  hostname=$HOST"
fi

echo "→ Firewall: allow LB health check + IAP tunnel to :8080…"
# LB health check + Google Front Ends: 35.191.0.0/16, 130.211.0.0/22
gcloud --project=$PROJECT compute firewall-rules create ${NAME_PREFIX}-allow-lb \
   --network=${NAME_PREFIX}-vpc \
   --direction=INGRESS --action=allow --rules=tcp:8080 \
   --source-ranges=35.191.0.0/16,130.211.0.0/22 \
   --target-tags=${NAME_PREFIX} 2>/dev/null || true

# IAP tunnels come from 35.235.240.0/20
gcloud --project=$PROJECT compute firewall-rules create ${NAME_PREFIX}-allow-iap \
   --network=${NAME_PREFIX}-vpc \
   --direction=INGRESS --action=allow --rules=tcp:22 \
   --source-ranges=35.235.240.0/20 \
   --target-tags=${NAME_PREFIX} 2>/dev/null || true

echo "→ Tagging VM $VM_NAME with ${NAME_PREFIX}…"
gcloud --project=$PROJECT compute instances add-tags $VM_NAME --zone=$VM_ZONE --tags=${NAME_PREFIX} 2>/dev/null || true

echo "→ Instance group (unmanaged)…"
gcloud --project=$PROJECT compute instance-groups unmanaged create ${NAME_PREFIX}-ig --zone=$VM_ZONE 2>/dev/null || true
gcloud --project=$PROJECT compute instance-groups unmanaged add-instances ${NAME_PREFIX}-ig \
  --zone=$VM_ZONE --instances=$VM_NAME 2>/dev/null || true
gcloud --project=$PROJECT compute instance-groups unmanaged set-named-ports ${NAME_PREFIX}-ig \
  --zone=$VM_ZONE --named-ports=http:8080 2>/dev/null || true

echo "→ Health check (TCP :8080)…"
gcloud --project=$PROJECT compute health-checks create tcp ${NAME_PREFIX}-hc --port=8080 2>/dev/null || true

echo "→ Backend service (86400s timeout for long streams)…"
gcloud --project=$PROJECT compute backend-services create ${NAME_PREFIX}-bs \
   --global --protocol=HTTP --port-name=http --health-checks=${NAME_PREFIX}-hc \
   --timeout=86400 2>/dev/null || true
gcloud --project=$PROJECT compute backend-services add-backend ${NAME_PREFIX}-bs \
  --global --instance-group=${NAME_PREFIX}-ig --instance-group-zone=$VM_ZONE 2>/dev/null || true
gcloud --project=$PROJECT compute backend-services update ${NAME_PREFIX}-bs --global --timeout=86400 2>/dev/null || true

echo "→ Google-managed SSL cert for $HOST…"
# Name the cert per-hostname so changing domain doesn't collide with the
# old cert (Google-managed certs are immutable — you can't change domains).
CERT_NAME="${NAME_PREFIX}-cert-$(echo "$HOST" | tr '.' '-' | tr '[:upper:]' '[:lower:]' | cut -c1-50)"
gcloud --project=$PROJECT compute ssl-certificates create $CERT_NAME \
   --global --domains=$HOST 2>/dev/null || true

echo "→ URL map, target HTTPS proxy (using cert $CERT_NAME), forwarding rule…"
gcloud --project=$PROJECT compute url-maps create ${NAME_PREFIX}-um --default-service=${NAME_PREFIX}-bs 2>/dev/null || true

if gcloud --project=$PROJECT compute target-https-proxies describe ${NAME_PREFIX}-tp --global >/dev/null 2>&1; then
  # Update cert if it's different from current binding
  CUR_CERT=$(gcloud --project=$PROJECT compute target-https-proxies describe ${NAME_PREFIX}-tp --global --format='value(sslCertificates)' 2>/dev/null | tr ',' '\n' | xargs -r -n1 basename || true)
  if [ "$CUR_CERT" != "$CERT_NAME" ]; then
    echo "  swapping cert on target proxy: $CUR_CERT → $CERT_NAME"
    gcloud --project=$PROJECT compute target-https-proxies update ${NAME_PREFIX}-tp \
      --global --ssl-certificates=$CERT_NAME 2>/dev/null || true
  fi
else
  gcloud --project=$PROJECT compute target-https-proxies create ${NAME_PREFIX}-tp \
     --global --ssl-certificates=$CERT_NAME --url-map=${NAME_PREFIX}-um 2>/dev/null || true
fi
gcloud --project=$PROJECT compute forwarding-rules create ${NAME_PREFIX}-fr \
   --global --address=${NAME_PREFIX}-ip --target-https-proxy=${NAME_PREFIX}-tp --ports=443 2>/dev/null || true

echo "→ Enabling IAP on backend service…"
gcloud --quiet --project=$PROJECT services enable iap.googleapis.com 2>/dev/null || true
gcloud --quiet --project=$PROJECT iap oauth-brands create \
  --application_title="Antigravity Web Hub" \
  --support_email=$(gcloud config get-value account 2>/dev/null) 2>/dev/null || true
gcloud --quiet --project=$PROJECT compute backend-services update ${NAME_PREFIX}-bs --global --iap=enabled 2>/dev/null || true

echo "→ Granting IAP HTTPS resource accessor to $IAP_USERS…"
IFS=',' read -ra USERS <<< "$IAP_USERS"
for u in "${USERS[@]}"; do
  gcloud --quiet --project=$PROJECT iap web add-iam-policy-binding \
    --resource-type=backend-services --service=${NAME_PREFIX}-bs \
    --member="$u" --role=roles/iap.httpsResourceAccessor 2>/dev/null || true
done

echo
echo "✅ Done."
echo "   Public URL : https://$HOST/  (waits up to ~15 min for cert provisioning)"
echo "   IAP users  : $IAP_USERS"
echo
echo "Add to .env:"
echo "   PUBLIC_HOSTNAME=$HOST"
