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

## 🚀 Quick Start Deployment

```bash
# 1. Navigate to the terraform directory
cd terraform

# 2. Copy variables template
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars

# 3. Initialize & Apply
terraform init
terraform plan
terraform apply
```

---

## 🔗 Post-Deployment Configuration

1. **SSH into the VM via IAP**:
   ```bash
   gcloud compute ssh antigravity-web-hub --project=<YOUR_PROJECT_ID> --zone=us-central1-a --tunnel-through-iap
   ```

2. **Run Web Hub Installer**:
   ```bash
   git clone https://github.com/cloud-gtm/antigravity-web-hub.git
   cd antigravity-web-hub
   ./scripts/install.sh
   ```

3. **Access the Web UI**:
   Open the `public_url` output from Terraform (e.g. `https://<ip>.nip.io/`). Note that Google-managed SSL certificates take ~10-15 minutes to finish DNS validation and activate.
