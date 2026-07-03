# Antigravity Web Hub

Run [Google Antigravity's](https://antigravity.google/) web hub on a headless GCP VM with optimized direct-to-Go routing and native extensions:

- **Optimized Native Performance.** The FastAPI proxy has been completely removed. High-performance streaming RPCs and assets go directly from Nginx to Google's native Go `language_server` with zero intermediate proxy hops or latency.
- **Model Ingress via Vertex AI sidecar.** A lightweight Python sidecar (`ccpa_mock.py` on port `8083`) intercepting specific unary paths to perform model list augmentation and routing to Vertex AI via Google Application Default Credentials (ADC).
- **Integrated Google Workspace MCP Server.** Natively runs a Google Workspace MCP server under standard OAuth, allowing the language server to write spreadsheets, schedule events, check mail, and index drive files asynchronously without client browser dependencies. Highly secure head-less profile isolation with tokens persisted in `tokens.json`.
- **On-demand FastMCP `deep_research` tool.** Exposes a Python FastMCP server (Streamable HTTP + SSE) natively configured inside `mcp.json` that performs intensive research loops using Google Gemini.

The point isn't to fork Antigravity — it's to make it a first-class tool on a shared server, utilizing native capabilities and official APIs.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full diagram and component walkthrough. TL;DR:

```
Browser → GCP HTTPS LB (IAP) → nginx :8080
                                 ├── GetUserStatus & StartCascade → ccpa_mock.py :8083
                                 └── Everything else → language_server :8081
```

## Prerequisites

- A Debian/Ubuntu VM in GCP with:
  - Application Default Credentials configured
    (`gcloud auth application-default login` — see [SETUP.md](SETUP.md))
  - A publicly-reachable hostname / IP (the setup script wires up a Classic HTTPS Load Balancer + IAP)
  - A second data disk **strongly recommended** — boot disk fills up fast. The install script formats and mounts it at `/mnt/data` if present.
- Antigravity CLI installed (`~/.gemini/antigravity/bin/language_server`, `agy`). The install script fetches the public installer.

## Installation & Deployment

For a zero-friction, automated deployment from your local workstation, or for step-by-step manual setup instructions, please see the comprehensive **[SETUP.md](SETUP.md)** guide.

### Quick Start (One-Shot Bootstrap)

The quickest way to deploy the entire Web Hub (VM, Load Balancer, SSL certs, and IAP Auth) is using our one-shot workstation orchestrator:

```bash
# 1. Clone the repository
git clone https://github.com/gmilen-sketch/antigravity-web-hub.git
cd antigravity-web-hub

# 2. Configure your environment
cp .env.example .env
nano .env

# 3. Provision and deploy
./scripts/bootstrap_all.sh
```

For more details on OAuth configurations, systemd administration, or advanced GCP VM customization, refer to **[SETUP.md](SETUP.md)**.

## Using it

- **Pick a model** from the dropdown (bottom-right of the input). Gemini models route directly through the native Go server to Vertex AI.
- **Run Google Workspace actions** — Ask Gemini to list drive files, send emails, or check calendar events.
- **Conversations persist.** Restart `antigravity-web.service` — your Gemini cascades come back from agy's own SQLite store.

## Docs

- **[SETUP.md](SETUP.md)** — Step-by-step deployment guide & Workspace OAuth setup
- [ARCHITECTURE.md](ARCHITECTURE.md) — Component diagram and design details
- [docs/request-flow.md](docs/request-flow.md) — End-to-end walkthrough of one turn
- [docs/mcp.md](docs/mcp.md) — Adding your own MCP tools
- [docs/custom-domain.md](docs/custom-domain.md) — Swapping `<ip>.nip.io` for a real DNS domain
- [docs/troubleshooting.md](docs/troubleshooting.md) — Known failure modes and operations runbook

## Contributions & scope

The project is intentionally small and lightweight — a simple Nginx configuration, a sidecar Python process, and a systemd unit. If you want to add or modify model settings, follow the pattern in `src/ccpa_mock.py`'s `DROPDOWN_MODELS` and `map_model_name`.

## License

MIT — see [LICENSE](LICENSE).
