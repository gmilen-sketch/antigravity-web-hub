# Zero-Touch Enterprise Customer PoC Playbook: Antigravity Web Hub v3.9.0 on Google Cloud

* **Maintainers:** Open-Source Cloud Architecture Maintainers (`maintainer@example-enterprise.com`)
* **Document Version:** v3.9.0 (November 2026) — Clean-Room Enterprise Sandbox Edition (`Antigravity Core 2.29.1` + `CLI 1.5.3` + `8-Model GA Roster`)
* **Canonical Repository:** `https://github.com/GoogleCloudPlatform/antigravity-web-hub` (`v3.9.0`)

---

## 1. Commercial & Technical Synergy: Isolated GCP Trial Projects + Antigravity Web Hub v3.9.0

Enterprise organizations evaluating agentic software engineering frequently encounter two operational blockers: procurement delays when provisioning an isolated sandbox Google Cloud project, and strict endpoint lockdowns (VDI / MDM policies) that block developers from installing desktop IDE binaries or local CLI tokens on corporate laptops.

Deploying **Antigravity Web Hub (`v3.9.0`)** inside an isolated Google Cloud trial or sandbox project resolves both constraints in a single automated workflow. Antigravity Web Hub serves a browser-accessible, Identity-Aware Proxy (IAP) protected agentic IDE running entirely inside the customer's isolated GCP project with full **8-Model GA support led by Gemini 4 Argon GA and Gemini 3.5 Flash**.

* **Zero Endpoint Binary Blockers:** Serves the Antigravity `2.29.1` Web UI over HTTPS (`:443`) so a cohort of **15 to 25** customer developers can onboard via browser SSO in under **2 minutes** with **0** laptop installations.
* **Zero Internal Contamination:** Verified by an automated clean-room test and IP hygiene suite (`tests/test_autonomy_kg_hooks.py` & `src/hooks/black_hat_analyzer.py`) enforcing **0** internal paths, **0** proprietary credentials, and **0** binary blobs.
* **Dynamic 8-Model GA Roster (`131,072` Max Output Cap):** Switch seamlessly across **8 GA models** (`Gemini 4 Argon` default on enum `354` with `sanitize_gemini_4_payload()`, `Gemini 3.8 Flash` on `352`, `Gemini 3.5 Flash` on `350`, `Gemini 3.6 Flash` on `348`, `Gemini 3.5 Flash Lite` on `330`, `Claude Opus 5.5` on `290`, `Claude Sonnet 5.5` on `333`, and `Claude Fable 5` on `340`) backed strictly by the customer VM's Vertex AI Application Default Credentials (ADC).

## 2. Deployment Model Comparison: Local Desktop vs. Cloud-Hosted Web Hub v3.9.0

| Pilot Dimension | Option A: Local Desktop Binary Install | Option B: Cloud-Hosted Antigravity Web Hub (`v3.9.0`) | Operational Advantage |
| :--- | :--- | :--- | :--- |
| **Developer Onboarding & Laptop Lockdowns** | Every developer downloads binaries from `antigravity.google` and configures local workstation ADC<br/>• Blocked by strict VDI or MDM endpoint policies in regulated enterprises | Serves Antigravity Core `2.29.1` + CLI `1.5.3` over HTTPS (`:443`) from a dedicated Shielded GCE VM (`c2-standard-16`)<br/>• Developers sign in via Google Cloud IAP with **0** local binary installation | Cuts onboarding lead time from **2–5 days** (endpoint security approval) to **under 2 minutes** via browser URL. |
| **Shared Team Governance, Skills & MCPs** | Each workstation starts empty unless developers manually clone rules, skills, and MCP configs | Pre-loads **20** `PD-Q` skills, **8** FastMCP servers, **4** deterministic hooks (`PreInvocation`, `PostInvocation`, `PreToolUse`, `Stop`), **5** subagents, and **5** pre-warmed enterprise sessions via `/api/sessions` | Guarantees **100%** team consistency across every pilot participant from Turn 1. |
| **Model Access & Credential Isolation** | Requires per-seat `gcloud auth application-default login` tokens stored on developer laptops | Routes all **8 GA models** (`Gemini 4 Argon`, `Gemini 3.8 Flash`, `Gemini 3.5 Flash`, `Gemini 3.6 Flash`, `Gemini 3.5 Flash Lite`, `Claude Opus/Sonnet 5.5`, `Claude Fable 5`) via least-privilege GCE VM Service Account ADC | Zero developer laptop tokens; **100%** Vertex AI traffic remains inside the customer GCP project. |

## 3. Clean-Room 4-Zone Reference Architecture & Custom OAuth 2.0 IAP Runbook

* **Zone 1 — Global HTTPS Load Balancer & Custom OAuth 2.0 IAP Perimeter (`:443`):** An External Application Load Balancer terminates TLS using a Google-managed SSL certificate (`<STATIC_IP>.nip.io`) and enforces Identity-Aware Proxy (IAP) authentication before any request reaches the VM.
* **Zone 2 — Shielded VM & Tenant Governance:** Runs on a Shielded GCE VM (`constraints/compute.requireShieldedVm`, OS Login enabled, zero public VM IP via Cloud NAT + Private Google Access) using a least-privilege service account (`roles/aiplatform.user`, `roles/bigquery.user`, `roles/logging.viewer`).
* **Zone 3 — 8-Model GA Vertex AI Router (`ccpa_mock.py` `127.0.0.1:8083`):** Translates Connect-RPC / gRPC-Web requests to Vertex AI (`131,072` max output tokens for Gemini 4 / 3.8 / 3.6; `65,535` for Gemini 3.5 Flash / Lite; `16,384` for Claude 5.5), strips unsupported Gemini 4 parameters via `sanitize_gemini_4_payload()`, and binds strictly to loopback (`AGW_BIND_HOST=127.0.0.1`).
* **Zone 4 — Antigravity Web Hub (`v3.9.0`) Runtime & 4-Hook Autonomy Plane (`:8080/:8081/:8084`):** Nginx (`:8080`) injects `bootstrap.js`, proxies to headless Go `language_server` (`2.29.1` on `:8081`), runs **8** FastMCP servers, and enforces `HookSystemMessage` `PreInvocation` grounding, zero-token `PostInvocation` verification banners, `force_ask` `PreToolUse` safety mediation, and Adaptive `K=1..3` `[SHARD:<id>]` Goldfish $\rightarrow$ Holistic Judge `Stop` verification.

### 3.1 Resolving IAP Error 604 (`RESOURCE_DASHER_CUSTOMER_ID_MISSING`) on Domainless Trial Projects

Google Cloud trial organizations created without Google Workspace domain verification lack a `directoryCustomerId`, causing default IAP activation to return `Error 604: RESOURCE_DASHER_CUSTOMER_ID_MISSING`. Complete these 4 steps inside the customer's GCP Console:

1. **Step 1 — Provision VPC, Shielded VM & One-Command Installer:** Provision the VPC + Cloud NAT + Shielded VM (`terraform apply` or `scripts/gcp_setup_vm.sh`), clone `antigravity-web-hub`, and execute `sudo bash scripts/install.sh` to install Antigravity Core `2.29.1`, CLI `1.5.3`, and the `v3.9.0` autonomy bundle.
2. **Step 2 — Configure External OAuth Consent Screen:** In **APIs & Services > OAuth consent screen**, choose **External** user type, set the application name to `Antigravity Web Hub PoC`, and add authorized pilot tester email addresses.
3. **Step 3 — Create Custom Web Application OAuth 2.0 Client:** In **APIs & Services > Credentials > Create Credentials > OAuth client ID**, select **Web application** and add `https://iap.googleapis.com/v1/oauth/clientIds/<CLIENT_ID>:handleRedirect` under **Authorized redirect URIs**.
4. **Step 4 — Bind Custom OAuth Client to IAP & Grant Access:** Run `gcloud compute backend-services update antigravity-backend --global --iap=enabled,oauth2-client-id=<CLIENT_ID>,oauth2-client-secret=<CLIENT_SECRET>` and grant `roles/iap.httpsResourceAccessor` to pilot participants.

| Component Layer | Technical Specification & Port | Clean-Room Security & Isolation Control |
| :--- | :--- | :--- |
| **Ingress & Identity (`:443`)** | External HTTPS Application LB + Managed SSL (`<IP>.nip.io`) + Custom OAuth 2.0 IAP | Blocks unauthenticated traffic at Google edge; resolves trial `Error 604` via External OAuth client |
| **Web Proxy & State (`:8080`)** | Nginx reverse proxy + `/var/www/html/bootstrap.js` + `/mnt/data/projects/persistent_ui_sessions.json` | Rewrites `Host: 127.0.0.1:8081`; synchronizes shared sessions via `/api/sessions` |
| **Core Agent Engine (`:8081`)** | Headless Go `language_server` (`2.29.1`) + `antigravity` CLI (`1.5.3`) + SQLite WAL stores | Runs under non-root OS Login user; `run_hook_safe.sh` enforces `PYTHONSAFEPATH=1` & zero `.pyc` |
| **8-Model & Autonomy Plane (`:8083/:8084`)** | `ccpa_mock.py` (`127.0.0.1:8083`) + **8** FastMCPs + **20** `PD-Q` skills + **4** hooks + **5** subagents | Uses customer VM ADC only; enforces `force_ask` destructive/config guard & `GOLDFISH-RO-1` sandbox |

## 4. Pre-Warmed Enterprise User Journeys (`src/bootstrap.js`)

1. **Journey 1 — Executive Operations Briefing:** Triages multi-channel engineering milestones, drafts concise status updates, and schedules follow-up action items (`Gemini 3.8 Flash`).
2. **Journey 2 — DevOps & GitOps Infrastructure Audit:** Audits GKE Autopilot Terraform modules, Cloud Armor WAF policies, Workload Identity Federation, and canary rollouts (`Claude Sonnet 5.5`).
3. **Journey 3 — Agentic Cloud SRE Incident RCA:** Diagnoses regional `P99` payment-gateway latency degradation and generates Istio `DestinationRule` circuit breakers + Terraform traffic drains (`Claude Opus 5.5`).
4. **Journey 4 — FinOps & BigQuery Spend Analytics:** Queries `synthetic_analytics.cloud_billing_summary` and `support_cases` in BigQuery to quantify CUD savings and partition pruning (`Gemini 3.8 Flash`).
5. **Journey 5 — Autonomous Agent Harness Deep Dive:** Walks through the 4-Pillar clean-room harness architecture (`/dev/shm` Bitemporal KG, `PreToolUse` Sentinel, Adaptive Goldfish $\rightarrow$ Judge, and `00:30 UTC` Nightly Dreaming).

## 5. 4-Week Enterprise Customer Pilot Rollout Checklist

| Pilot Week | Milestone & Owner | Verification Gate & Exit Criteria |
| :--- | :--- | :--- |
| **Week 1: Sandbox Provisioning** | Customer Cloud Platform Admin deploys Terraform / `scripts/install.sh` + Custom OAuth IAP | `/healthz` returns `ok`, `/api/version` confirms Core `2.29.1` & Hub `3.9.0`, and `black_hat_analyzer.py --target .` passes (`0` leaks) |
| **Week 2: Guided Team Onboarding** | Onboard 15–25 developers into `enterprise-workspace` across the 5 seeded journeys | `node scripts/verify_e2e.js` passes all 8 GA model selector and live Vertex AI streaming checks |
| **Week 3: Domain Repository Sprint** | Connect non-production customer Git repositories and customize `skills/` + `kb/` (`OKF v0.2`) | Paired harness evaluation (`python3 -B scripts/run_ab_benchmark.py --self-test`) passes all deterministic & safety checks |
| **Week 4: Security Review & Tear-Down / Scale-Out** | Export architecture findings, audit Cloud Logging BAIC attribution, or destroy zero-cost trial resources | Run `scripts/gcp_destroy.sh` for zero residual sandbox billing, or promote Terraform module to enterprise production VPC |
