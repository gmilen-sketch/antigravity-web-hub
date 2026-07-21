# Antigravity Web Hub Setup & Deployment Guide

This guide is designed for **Cloud Engineers (CEs)** and **SREs** to deploy and configure the Antigravity 2.0 Standalone Web Hub with minimal friction.

We provide three deployment options:
* **Option A (Recommended): One-Shot Automated Terraform Module** – Provision everything declaratively with 100% Argolis Org Policy compliance (Shielded VM, OS Login, IAP Load Balancer, custom subnets).
* **Option B: One-Shot Workstation Script (`bootstrap_all.sh`)** – Orchestrates GCE VM, LB, and SSL certificates from your local terminal.
* **Option C: Manual VM-Side Installation** – For cases where you already have a configured VM and want to run the installer locally.

---

## Prerequisites

Before starting, ensure your local workstation has:
1. **Google Cloud SDK (`gcloud`)** installed and authenticated:
   ```bash
   gcloud auth login
   ```
2. **Owner or Editor permissions** on your target GCP project (required to create Load Balancers, IAP OAuth brands, and GCE instances).

---

## Option A: One-Shot Automated Terraform Module (Argolis Ready - Recommended)

This option uses Terraform to provision the complete infrastructure declaratively, adhering to all default Argolis security policies (`compute.requireShieldedVm`, `compute.requireOsLogin`, `compute.vmExternalIpAccess`, `compute.skipDefaultNetworkCreation`), and automatically binds `roles/aiplatform.user` for Vertex AI model streaming.

### 1. Clone & Navigate to `terraform/`
```bash
git clone https://github.com/cloud-gtm/antigravity-web-hub.git
cd antigravity-web-hub/terraform
```

### 2. Configure `terraform.tfvars`
```bash
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars
```
Set `project_id` to your Argolis project ID and `iap_members` to your email:
```hcl
project_id  = "your-argolis-project-id"
zone        = "us-central1-a"
iap_members = ["user:you@example.com"]
```

### 3. Deploy Infrastructure
```bash
terraform init
terraform apply -auto-approve
```

### 4. Bootstrap Web Hub Software
Return to the repository root and deploy the software package to the newly created VM automatically:
```bash
cd ..
./scripts/bootstrap_all.sh
```

Your web hub will be accessible at the `public_url` printed by Terraform (e.g. `https://<ip>.nip.io/`).


---

## Option B: One-Shot Workstation Script (`bootstrap_all.sh`)

This method provisions and wires up everything from your workstation. No manual VM ssh/configuration is required.

### 1. Clone the Repository
```bash
git clone https://github.com/gmilen-sketch/antigravity-web-hub.git
cd antigravity-web-hub
```

### 2. Configure Environment Variables
Copy the template and edit the `.env` file:
```bash
cp .env.example .env
nano .env
```

Fill in the following fields:
* `GOOGLE_CLOUD_PROJECT`: Your target GCP Project ID.
* `VM_NAME`: Desired GCE instance name (e.g., `antigravity-web-hub`).
* `VM_ZONE`: Target zone (e.g., `us-central1-a`).
* `IAP_USERS`: Comma-separated list of Google accounts allowed to access the Web Hub (e.g., `user:alice@yourcorp.com,group:eng-team@yourcorp.com`).
* `CSRF_TOKEN`: Generate a secure unique token (e.g., run `openssl rand -hex 32` and paste it).
* *(Optional)* `PUBLIC_DOMAIN`: If you have a custom domain, add it here and point its DNS `A` record to the IP address output during the build. (If left blank, a `<ip>.nip.io` domain will be created automatically).

### 3. Run the Bootstrap Orchestrator
Execute the bootstrap script on your local workstation:
```bash
./scripts/bootstrap_all.sh
```

**What this script does behind the scenes:**
1. Spawns a Debian 12 GCE VM with a dedicated 100 GB persistent data disk.
2. Allocates a static global IP and provisions a Google-managed SSL certificate.
3. Sets up a Global Classic HTTPS Load Balancer.
4. Activates IAP (Identity-Aware Proxy) on the backend to enforce secure single sign-on (SSO).
5. Copies this repository's code to the VM using `gcloud compute scp`.
6. Triggers the VM's internal installer (`scripts/install.sh`) to wire up Nginx, systemd, dependencies, and launch the server.

*Note: Google's SSL provisioning can take up to 15 minutes on the first run. The console will display progress.*

---

## Option B: Manual VM-Side Installation

Use this if you already have an existing Debian/Ubuntu VM on GCP.

### 1. Provision / Access your GCE VM
Ensure your GCE VM is created with the `cloud-platform` API scope so the instance can retrieve Application Default Credentials (ADC) natively:
```bash
# If creating a new VM manually:
gcloud compute instances create my-hub-vm \
  --zone=us-central1-a \
  --scopes=cloud-platform \
  --tags=antigravity-web
```

### 2. Clone and Configure
SSH into your GCE VM, clone the repository, and set up your `.env`:
```bash
gcloud compute ssh my-hub-vm --zone=us-central1-a --tunnel-through-iap

git clone https://github.com/gmilen-sketch/antigravity-web-hub.git
cd antigravity-web-hub
cp .env.example .env
nano .env
```
*(Configure the `GOOGLE_CLOUD_PROJECT` and `CSRF_TOKEN` as described in Option A).*

### 3. Run the Installer
Run the installer script with `sudo -E` (keeps the environment variables, allowing the installer to read your configured `.env` file):
```bash
sudo -E scripts/install.sh
```

The installer will configure Nginx as a reverse proxy, register the `antigravity-web.service` systemd unit, and launch both the native Go server and python CCPA sidecar.

---

## Enabling Google Workspace MCP Integration (Optional)

The Web Hub includes a headless, native Google Workspace MCP integration. To enable it:

### 1. Generate Google OAuth Credentials
1. Go to the **GCP Console** -> **APIs & Services** -> **Credentials**.
2. Click **Create Credentials** -> **OAuth client ID**.
3. Select Application Type: **Web application**.
4. Add authorized redirect URIs:
   - `https://vertexaisearch.cloud.google.com/static/oauth/oauth.html`
   - `https://pantheon.corp.google.com/connectors/oauth?project=YOUR_PROJECT_ID`
5. Click **Create** and copy your **Client ID** and **Client Secret**.

### 2. Add to Environment
Paste the credentials into your `.env` file:
```env
OAUTH_CLIENT_ID=your-oauth-client-id.apps.googleusercontent.com
OAUTH_CLIENT_SECRET=your-oauth-client-secret
```

### 3. Restart the Service
To apply the changes:
```bash
sudo systemctl restart antigravity-web.service
```

---

## Administration & Monitoring

Here are the critical commands you or your peers need to manage and monitor the service:

### View Web Hub Logs
The `antigravity-web.service` manages both the native Go server and the Python `ccpa_mock.py` sidecar:
```bash
# Stream all systemd logs
journalctl -u antigravity-web.service -f

# View raw logs from the sidecar's Vertex AI requests
tail -f /tmp/ccpa_mock.log
```

### Service Control
```bash
# Restart the Hub (Go + Sidecar)
sudo systemctl restart antigravity-web.service

# Check service health
sudo systemctl status antigravity-web.service --no-pager
```

### Manage Chromium Locks (If the interface hangs)
If Chromium crashes, it can leave lockfiles on GCE VMs that prevent the browser tools from launching. Run this clean sweep:
```bash
# 1. Kill zombie Chrome instances
sudo pkill -9 -f chrome || true

# 2. Delete stale lockfiles
rm -rf /tmp/ls-chrome-data/*
rm -f ~/.config/chrome-data/Singleton*
rm -f ~/.config/chrome-data/DevToolsActivePort.lock

# 3. Restart Web Hub
sudo systemctl restart antigravity-web.service
```
