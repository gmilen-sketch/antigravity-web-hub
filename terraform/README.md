# Antigravity Web Hub - Terraform Module (Argolis & Enterprise Ready)

This Terraform module provisions the complete infrastructure for **Antigravity Web Hub** on GCP out of the box, fully compliant with **Argolis Organization Policies** and enterprise security guardrails.

---

## 🛡️ Argolis Policy Compliance Included

This module handles the key security constraints enforced in Argolis self-managed and temporary projects:
1. **Shielded VM Enforcement (`compute.requireShieldedVm`)**: Enables Secure Boot, vTPM, and Integrity Monitoring on the GCE instance.
2. **OS Login Enforcement (`compute.requireOsLogin`)**: Sets `enable-oslogin = TRUE`.
3. **No Direct External IP (`compute.vmExternalIpAccess`)**: Keeps the GCE VM strictly internal without a public IP on its interface. Traffic is securely routed through the Global HTTPS Load Balancer, and SSH is handled via IAP Tunneling.
4. **No Service Account Key Export (`iam.disableServiceAccountKeyCreation`)**: Relies on VM default service accounts and Application Default Credentials (ADC).
5. **Custom Subnetwork (`compute.skipDefaultNetworkCreation`)**: Explicitly provisions a dedicated VPC and Subnet.

---

## 🚀 1-Click CE Deployment Guide

Deploying Antigravity Web Hub in an Argolis or sandbox GCP project takes under **3 minutes**:

```bash
# 1. Clone & navigate to terraform directory
git clone https://github.com/cloud-gtm/antigravity-web-hub.git
cd antigravity-web-hub/terraform

# 2. Configure variables
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars
```

Set your project ID and user email in `terraform.tfvars`:
```hcl
project_id  = "your-argolis-project-id"
zone        = "us-central1-a"
iap_members = [
  "user:you@example.com"
]
```

```bash
# 3. Provision Infrastructure (VPC, NAT, VM, Load Balancer, IAP & Vertex AI IAM)
terraform init
terraform apply -auto-approve

# 4. Bootstrap Web Hub Software on VM
cd ..
./scripts/bootstrap_all.sh
```

---

## 🔗 Accessing the Application

- **Web UI URL**: Open the `public_url` output from Terraform (e.g. `https://<ip>.nip.io/`).
  *(Note: Google-managed SSL certificates take ~10-15 minutes to provision).*
- **IAP SSH Command**:
  ```bash
  gcloud compute ssh antigravity-web-hub --project=<YOUR_PROJECT_ID> --zone=us-central1-a --tunnel-through-iap
  ```

