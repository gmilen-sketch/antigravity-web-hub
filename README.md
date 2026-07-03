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

## Quick start

```bash
# ONE-SHOT — creates VM + LB + IAP + installs hub (from workstation):
git clone https://github.com/gmilen-sketch/antigravity-web-hub
cd antigravity-web-hub
cp .env.example .env && $EDITOR .env
scripts/bootstrap_all.sh
```

Or do it in two stages — provision GCP on your workstation, then log into the VM and install:

```bash
# 1. Clone
git clone https://github.com/gmilen-sketch/antigravity-web-hub
cd antigravity-web-hub

# 2. Copy the env template and fill it in
cp .env.example .env
$EDITOR .env

# 3. Install (idempotent — safe to re-run)
sudo -E scripts/install.sh
```

That's it. The install script:

1. Installs the Antigravity CLI (Google's public installer) if not present.
2. `pip install --user`s the Python deps.
3. `npm install`s the Google Workspace MCP dependencies.
4. Formats and mounts `/dev/sdb` at `/mnt/data` if the disk exists and is empty (asks first).
5. Drops `nginx.conf` and reloads nginx.
6. Templates the systemd unit with your `$USER`, installs `/etc/antigravity-web.env` from your `.env`, and starts the service.

Visit `https://<your-hostname>/` — you should see the Antigravity SPA with a model dropdown containing **Gemini 3.5 Flash**, **Gemini 3.1 Flash Lite Preview**, and **Gemini 3.1 Pro**.

## Using it

- **Pick a model** from the dropdown (bottom-right of the input). Gemini models route directly through the native Go server to Vertex AI.
- **Run Google Workspace actions** — Ask Gemini to list drive files, send emails, or check calendar events.
- **Conversations persist.** Restart `antigravity-web.service` — your Gemini cascades come back from agy's own SQLite store.

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — component diagram and design details
- [docs/request-flow.md](docs/request-flow.md) — end-to-end walkthrough of one turn
- [docs/mcp.md](docs/mcp.md) — adding your own MCP tools
- [docs/custom-domain.md](docs/custom-domain.md) — swap `<ip>.nip.io` for a real DNS domain
- [docs/troubleshooting.md](docs/troubleshooting.md) — known failure modes

## Contributions & scope

The project is intentionally small and lightweight — a simple Nginx configuration, a sidecar Python process, and a systemd unit. If you want to add or modify model settings, follow the pattern in `src/ccpa_mock.py`'s `DROPDOWN_MODELS` and `map_model_name`.

## License

MIT — see [LICENSE](LICENSE).
