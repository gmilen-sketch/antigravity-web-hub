# Antigravity Web Hub

Run [Google Antigravity's](https://antigravity.google/) web hub on a headless
GCP VM, with two extensions the desktop app doesn't ship:

- **Vertex Claude models in the dropdown.** Claude Opus 4.8 and Claude Fable 5
  are plumbed in via a proxy shim that calls Vertex Anthropic directly,
  bypassing agy's Gemini-only allowlist. Full multi-turn history, web browsing
  tools (search + URL fetch, SSRF-guarded), and disk persistence so
  conversations survive service restarts. See
  [docs/claude-shim.md](docs/claude-shim.md) for what the shim is and
  how it works.
- **On-demand FastMCP `deep_research` tool.** Type `/mcp start` in chat to
  spawn a Python FastMCP server (Streamable HTTP + SSE) that runs a
  Claude-Opus-powered research loop with `standard` and `max` modes. When
  running, the tool becomes callable by the Claude cascade in the hub.

The point isn't to fork Antigravity — it's to make it a first-class
multi-model tool on a shared server, without hosting your own agent.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full diagram and component
walkthrough. TL;DR:

```
Browser → GCP HTTPS LB (IAP) → nginx → proxy.py (FastAPI)
                                          ├── auth mocks
                                          ├── model dropdown injection
                                          ├── Claude shim → Vertex Anthropic
                                          ├── /mcp start|stop|status
                                          └── passthrough → language_server (agy)
```

## Prerequisites

- A Debian/Ubuntu VM in GCP with:
  - Application Default Credentials configured
    (`gcloud auth application-default login` — see [SETUP.md](SETUP.md))
  - A publicly-reachable hostname / IP (the setup script wires up a Classic
    HTTPS Load Balancer + IAP)
  - A second data disk **strongly recommended** — boot disk fills up fast
    with Claude conversation JSON. The install script formats and mounts it
    at `/mnt/data` if present.
- Antigravity CLI installed (`~/.gemini/antigravity/bin/language_server`,
  `agy`). The install script fetches the public installer.

## Quick start

```bash
# ONE-SHOT — creates VM + LB + IAP + installs hub (from workstation):
git clone https://github.com/gmilen-sketch/antigravity-web-hub
cd antigravity-web-hub
cp .env.example .env && $EDITOR .env
scripts/bootstrap_all.sh
```

Or do it in two stages — provision GCP on your workstation, then log into
the VM and install:

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
3. `npm install`s the Node MCP stub.
4. Formats and mounts `/dev/sdb` at `/mnt/data` if the disk exists
   and is empty (asks first).
5. Drops `nginx.conf` and reloads nginx.
6. Templates the systemd unit with your `$USER`, installs
   `/etc/antigravity-web.env` from your `.env`, and starts the service.

Visit `https://<your-hostname>/` — you should see the Antigravity SPA with a
model dropdown containing **Gemini 3.5 Flash**, **Claude Opus 4.8**, and
**Claude Fable 5**.

## Using it

- **Pick a model** from the dropdown (bottom-right of the input). Claude
  models route through Vertex; Gemini routes through agy.
- **Ask a URL question** — Claude has built-in `fetch_url` and `web_search`
  tools. Try: *"Fetch https://example.com and tell me the h1."*
- **Run a research task** — type `/mcp start` first, then ask Claude to
  research something. It'll delegate via the `deep_research` MCP tool.
- **Conversations persist.** Restart `antigravity-web.service` — your Claude
  cascades come back from `/mnt/data/antigravity/claude_cascades/`. Gemini
  cascades come back from agy's own SQLite store.

## Slash commands

| Command | Effect |
|---|---|
| `/mcp start` | Spawn the deep-research MCP subprocess and register the tool |
| `/mcp stop` | Kill the MCP subprocess and un-register the tool |
| `/mcp status` | PID / port / uptime |

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — component diagram
- [docs/claude-shim.md](docs/claude-shim.md) — **what the Vertex Claude shim is and how it works** (start here if you're wondering how Claude got into a Gemini-only UI)
- [docs/request-flow.md](docs/request-flow.md) — end-to-end walkthrough of one turn
- [docs/mcp.md](docs/mcp.md) — adding your own MCP tools
- [docs/troubleshooting.md](docs/troubleshooting.md) — known failure modes

## Contributions & scope

The project is intentionally small — one proxy, one MCP, one systemd unit. If
you want to add another model backend, follow the pattern in
`src/proxy.py`'s `CLAUDE_MODELS` / `_call_vertex_claude` — copy, add a new
label to `DROPDOWN_MODELS`, and route in the shim.

## License

MIT — see [LICENSE](LICENSE).
