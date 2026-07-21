# Changelog

All notable changes to the **Antigravity Web Hub** project will be documented in this file.

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

