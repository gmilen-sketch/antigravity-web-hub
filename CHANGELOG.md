# Changelog

All notable changes to the **Antigravity Web Hub** project will be documented in this file.

---

## [2.1.0] - 2026-07-21

### 🚀 Added
- **1-Click Terraform Module**: Declarative infrastructure provisioning with Argolis policy compliance (`compute.requireShieldedVm`, `compute.requireOsLogin`, `compute.vmExternalIpAccess`, `compute.skipDefaultNetworkCreation`).
- **Automated Vertex AI IAM Binding**: Terraform module and setup scripts now automatically bind `roles/aiplatform.user` (`aiplatform.endpoints.predict`) to the Compute Engine default service account (`<project_number>-compute@developer.gserviceaccount.com`).
- **Standalone Go `language_server` Packaging**: Included the native 149MB Go server binary directly in `bin/language_server` inside the deployment package.

### 🛠️ Fixed
- **Auth RPC Interception & Onboarding Bypass**: Added Nginx location rules for `GetAuthStatus`, `HasAuthToken`, `LoginWithBrowser`, `fetchUserInfo`, `loadCodeAssist`, `fetchAdminControls`, and `fetchAvailableModels` proxying to `ccpa_mock.py` (`:8083`), fixing SPA client-side redirects to `/onboarding`.
- **CSRF Token Alignment**: Standardized `CSRF_TOKEN=antigravity_secret_csrf_token_12345` across `.env.example`, `start_hub.sh`, `/etc/antigravity-web.env`, and `config/nginx.conf`, eliminating `Grpc-Status: 16 (invalid CSRF token)` errors.
- **Model Dropdown Proto3 Choice Wrappers**: Formatted model choice enums (`348` Gemini 3.5 Flash, `330` Gemini 3.1 Flash Lite Preview, `343` Gemini 3.1 Pro) using `{choice: {case: "model", value: val}}` for `@bufbuild/protobuf` compatibility in the browser.
- **gcloud ECP Socket Leak Handling**: Added `pkill -9 -f "ecp"` and `pkill -9 -f "gcloud"` in retry wrappers to resolve `[Errno 98] Address already in use` socket errors.
- **Terraform Unmanaged Instance Group Self-Link**: Fixed `instances` parameter in `google_compute_instance_group.unmanaged_ig` to use `google_compute_instance.hub_vm.self_link`.
