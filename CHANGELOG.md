# Changelog

All notable changes to the **Antigravity Web Hub** project will be documented in this file.

---

## [2.2.0] - 2026-07-22

### 🚀 Added
- **N4 Machine Type Family Migration**: Upgraded default VM machine type from `e2-standard-2` to `n4-standard-2` (5th Gen Intel Xeon Emerald Rapids) across Terraform (`variables.tf`, `terraform.tfvars`), setup scripts (`gcp_setup_vm.sh`), and environment configurations for significantly higher memory bandwidth and faster model routing.
- **Automated Google Cloud API Enablement**: Added declarative `google_project_service` resources in Terraform (`terraform/main.tf`) and automated `gcloud services enable` calls across all shell scripts (`scripts/gcp_setup_vm.sh`, `scripts/gcp_setup_lb.sh`). This automatically activates the 6 core required Google APIs on any fresh project:
  1. `compute.googleapis.com` (Compute Engine API)
  2. `iap.googleapis.com` (Cloud Identity-Aware Proxy API)
  3. `aiplatform.googleapis.com` (Vertex AI API)
  4. `iam.googleapis.com` (Identity and Access Management API)
  5. `cloudresourcemanager.googleapis.com` (Cloud Resource Manager API)
  6. `serviceusage.googleapis.com` (Service Usage API)

---

## [2.1.0] - 2026-07-21

### 🚀 Added
- **1-Click Terraform Module**: Declarative infrastructure provisioning with Argolis policy compliance (`compute.requireShieldedVm`, `compute.requireOsLogin`, `compute.vmExternalIpAccess`, `compute.skipDefaultNetworkCreation`).
- **Tier 2 Google CDN Binary Download Fallback**: Added automatic resolution in `bootstrap_all.sh` to download `Antigravity.tar.gz` directly from Google's official CDN (`https://edgedl.me.gvt1.com/...`) and extract `language_server` when deploying from a fresh workstation without local binaries.
- **Automated Vertex AI IAM Binding**: Terraform module and setup scripts now automatically bind `roles/aiplatform.user` (`aiplatform.endpoints.predict`) to the Compute Engine default service account (`<project_number>-compute@developer.gserviceaccount.com`).
- **Standalone Go `language_server` Packaging**: Included native Go server binary detection and packaging in `scripts/bootstrap_all.sh`.

### 🛠️ Fixed
- **Vertex AI GCE Metadata Server Token Resolution**: Updated `get_adc_token()` in `src/ccpa_mock.py` to query GCE Metadata Server (`http://metadata.google.internal/...`) first, guaranteeing `roles/aiplatform.user` IAM permissions for Vertex AI streaming model inference without relying on local workstation credentials.
- **Argolis Org Policy Domain Restrictions**: Added explicit guidance and comments in `terraform/terraform.tfvars.example` and `SETUP.md` specifying the use of Argolis Admin user accounts (`admin@...altostrat.com`) to comply with `constraints/iam.allowedPolicyMemberDomains`.
- **Auth RPC Interception & Onboarding Bypass**: Added Nginx location rules for `GetAuthStatus`, `HasAuthToken`, `LoginWithBrowser`, `fetchUserInfo`, `loadCodeAssist`, `fetchAdminControls`, and `fetchAvailableModels` proxying to `ccpa_mock.py` (`:8083`), fixing SPA client-side redirects to `/onboarding`.
- **CSRF Token Alignment**: Standardized `CSRF_TOKEN=antigravity_secret_csrf_token_12345` across `.env.example`, `start_hub.sh`, `/etc/antigravity-web.env`, and `config/nginx.conf`, eliminating `Grpc-Status: 16 (invalid CSRF token)` errors.
- **Model Dropdown Proto3 Choice Wrappers**: Formatted model choice enums (`348` Gemini 3.5 Flash, `330` Gemini 3.1 Flash Lite Preview, `343` Gemini 3.1 Pro) using `{choice: {case: "model", value: val}}` for `@bufbuild/protobuf` compatibility in the browser.
- **gcloud ECP Socket Leak Handling**: Added `pkill -9 -f "ecp"` and `pkill -9 -f "gcloud"` in retry wrappers to resolve `[Errno 98] Address already in use` socket errors.
- **Terraform Unmanaged Instance Group Self-Link**: Fixed `instances` parameter in `google_compute_instance_group.unmanaged_ig` to use `google_compute_instance.hub_vm.self_link`.

