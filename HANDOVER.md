# Antigravity Web Hub — Handover

Written 2026-07-02. Left as `~/HANDOVER.md` so agy sees it in any session
opened from `$HOME`. Latest source-of-truth lives in the GitHub repo:
**https://github.com/gmilen-sketch/antigravity-web-hub**

---

## What this is, in one paragraph

Google's Antigravity web hub, running on a headless GCP VM (`jumpstation`,
zone `us-central1-c`, project `<your-gcp-project>`), reachable at
**https://antigravity.customertests.info/** through a GCP Classic HTTPS
Load Balancer with IAP. The setup adds two things Antigravity doesn't
ship: (1) Claude Opus 4.8 + Fable 5 in the model dropdown via a Vertex
Anthropic shim, and (2) an on-demand FastMCP `deep_research` tool
launched by `/mcp start` in chat. All model calls (Gemini AND Claude)
go through the shim now — agy's own Gemini path is broken in "external
builds" (`GetChatMessage is unimplemented`).

## Live URL & endpoints

| What | Where |
|---|---|
| Public UI | https://antigravity.customertests.info/ |
| Old nip.io fallback (still valid) | https://34.8.231.67.nip.io/ |
| LB static IP | `34.8.231.67` (`antigravity-lb-ip`, reserved) |
| VM external IP | `34.59.86.142` (`jumpstation-static-ip`, reserved) |
| SSL cert (Google-managed, ACTIVE) | `antigravity-ssl-cert-customertests`, expires 2026-09-30 |
| SSL cert (self-signed nip.io) | `antigravity-ssl-cert-nipio` — also attached, kept as fallback |

## Repo

- **URL:** https://github.com/gmilen-sketch/antigravity-web-hub (public, MIT)
- Everything sensitive is env-driven — see `.env.example`. Repo has zero
  hardcoded IDs / tokens.
- `scripts/bootstrap_all.sh` is a one-shot re-deployer: VM → LB → IAP →
  install. Idempotent.

## VM / disk layout

- Boot disk `/dev/sda` — 10 GB, currently ~96% full (nothing runtime writes here anymore).
- Data disk `/dev/sdb` — 100 GB ext4, mounted at `/mnt/data` (fstab UUID).
  - `/mnt/data/antigravity/claude_cascades/*.json` — persistent shim cascades
    (Gemini + Claude, both use this path — the name is historical).
- agy's own conversation DBs — `~/.gemini/antigravity/conversations/*.db`
  and `~/.gemini/antigravity-cli/conversations/*.db`.

## Running services

- **systemd unit:** `antigravity-web.service`. Starts
  `~/.gemini/antigravity/bin/start_hub.sh` which supervises:
  - `python3 ~/.gemini/antigravity/bin/proxy.py` on :8082 (FastAPI)
  - `~/.gemini/antigravity/bin/language_server --standalone …` on :8081 (Go, Antigravity SDK binary — Google's public build)
- **nginx** listens on :8080, routes streaming RPCs → language_server,
  everything else → proxy.py. Config in `/etc/nginx/sites-available/default`.
- **MCP** — `~/.gemini/antigravity/bin/mcp_deep_research.py` on :8093,
  NOT started at boot. Launched on demand via `/mcp start` in chat.

## The shim (`proxy.py`) — mental model

Everything routes through the shim except HTML/SPA-asset serving.
Model dispatch is by `x-user-model` HTTP header (added by injected JS
that reads the dropdown label). Lookup table `SHIM_MODELS = GEMINI ∪
CLAUDE`. Each cascade entry has a `vendor` field; `_call_vertex(vendor,
…)` dispatches to `_call_vertex_gemini` (Vertex `generateContent`) or
`_call_vertex_claude` (Vertex `rawPredict`).

**Models exposed:**

| Label in dropdown | Vertex model | Endpoint |
|---|---|---|
| Gemini 3.5 Flash (default) | `gemini-3.5-flash` | `generateContent` |
| Gemini 3.1 Flash Lite Preview | `gemini-3.1-flash-lite-preview` | `generateContent` |
| Gemini 3.1 Pro | `gemini-3.1-pro-preview` | `generateContent` |
| Claude Opus 4.8 | `claude-opus-4-8` | `rawPredict` |
| Claude Fable 5 | `claude-fable-5` | `rawPredict` |

All models get the same tool set: `fetch_url`, `web_search` (both
SSRF-guarded), plus `deep_research` when MCP is running. Anthropic and
Gemini tool schemas differ; the shim translates.

## Common tasks

**Tail logs:**
```bash
journalctl -u antigravity-web.service -f
```

**Restart after code change:**
```bash
sudo systemctl restart antigravity-web.service
```

**Sync a code change back to the repo (from live source):**
```bash
cp ~/.gemini/antigravity/bin/proxy.py /mnt/data/antigravity-web-hub/src/proxy.py
# Then re-run the scrub block in the git commit script or:
cd /mnt/data/antigravity-web-hub && python3 - <<PY
import re
p = "src/proxy.py"; s = open(p).read()
s = s.replace("<your-gcp-project>", "\${GOOGLE_CLOUD_PROJECT}")
s = s.replace("${HOME}", "\${HOME}")
s = re.sub(r'"csrfToken=antigravity_secret_csrf_token_12345',
           r'f"csrfToken={os.environ.get(\'CSRF_TOKEN\', \'\')}',  s)
s = re.sub(r'"GOOGLE_CLOUD_PROJECT", "<your-gcp-project>"',
           r'"GOOGLE_CLOUD_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", "")', s)
s = s.replace("antigravity_secret_csrf_token_12345",
              r'os.environ.get("CSRF_TOKEN") or _die("CSRF_TOKEN env var required")')
open(p, "w").write(s)
PY
```

**Push to GitHub** (needs a PAT since gh isn't installed):
```bash
cd /mnt/data/antigravity-web-hub
export GH_TOKEN='ghp_…'
git remote set-url origin "https://gmilen-sketch:${GH_TOKEN}@github.com/gmilen-sketch/antigravity-web-hub.git"
git push origin main
git remote set-url origin https://github.com/gmilen-sketch/antigravity-web-hub.git
unset GH_TOKEN
```

**⚠ CRITICAL rule when editing the injected JS in proxy.py**
Any syntax error in that block crashes `<script>` parse, which drops
`window.nativeStorage`, which crashes the SPA into a white screen.
Always validate after editing:
```bash
sudo systemctl restart antigravity-web.service && sleep 3
curl -s --compressed http://127.0.0.1:8080/ > /tmp/idx.html
python3 -c "
import re; html = open('/tmp/idx.html').read()
for i,s in enumerate(re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.DOTALL)):
    open(f'/tmp/s{i}.js','w').write(s)"
for f in /tmp/s*.js; do node --check "$f"; done
```

Especially watch for `\n` inside Python single-quoted strings that
become literal newlines in emitted JS — need `\\n\\n` in Python source
to render as valid `\n\n` escape in JS.

**Add a new model backend** — copy the `_call_vertex_gemini` pattern
in `proxy.py`, add to the appropriate MODELS dict, extend
`DROPDOWN_MODELS`, and update injected JS `KNOWN_LABELS`. See
`docs/claude-shim.md` in the repo.

**Add a new MCP tool** — see `docs/mcp.md` in the repo.

## Known limitations / open work

1. **Sidebar click doesn't fully reopen a persisted cascade.** URL bar
   works and follow-ups sticky-route to the right vendor by cid, but the
   sidebar click into a cascade doesn't hydrate the SPA into it —
   likely needs `trajectoryMetadata` populated with a real
   `environmentId` on the summary. (Filed internally as task #17.)
2. **Folder picker uses File System Access API** — Chromium/Edge only.
   Firefox/Safari click is a no-op. Also: picks a folder on the
   client's machine, not the VM; the shim maps it to
   `/home/<user>/projects/<name>` as a *label*. If you actually need
   the files on the VM, you still need `gcloud scp`.
3. **Old conversations bucketed as `outside-of-project`** — 68 of ~123
   pre-fix conversations have that projectId literally embedded in
   agy's `.db` files. They appear in the "outside of project" sidebar
   bucket, not under Default project. Not fixable without rewriting
   agy's DBs; new conversations post-fix land correctly.
4. **agy's `--override_model_name=gemini-3.5-flash` flag** in
   `start_hub.sh` is now dead-code — nothing routes through agy for
   model calls. Could be removed for cleanliness.

## Auth & secrets

- ADC on the VM (`gcloud auth application-default …`) is the auth for
  Vertex. Token file at
  `~/.config/gcloud/application_default_credentials.json`.
- `CSRF_TOKEN` in `/etc/antigravity-web.env` — the injected SPA JS sends
  it as `x-codeium-csrf-token` and `language_server` validates it.
  Currently (the current running value — see `/etc/antigravity-web.env` on the VM) — rotate on any
  redeployment.
- IAP is enabled on the backend service. IAM binding grants
  `roles/iap.httpsResourceAccessor` to `<the deploying user's GCP account>`.
  Add more users with:
  ```bash
  gcloud iap web add-iam-policy-binding \
    --resource-type=backend-services --service=antigravity-backend \
    --member=user:<email> --role=roles/iap.httpsResourceAccessor
  ```

## Contacts

- Repo owner: `gmilen-sketch` (GitHub)
- VM owner: `<the deploying user's GCP account>` (GCP)
- Domain: `customertests.info` — registered at Squarespace (was Google
  Domains), DNS is delegated to Google Cloud DNS
  (`ns-cloud-d[1-4].googledomains.com`). The `antigravity` A record was
  added via Squarespace's DNS editor.

## Where to look first if something breaks

- **White screen** → injected JS syntax error. See "CRITICAL rule"
  above. Fetch `/`, extract `<script>` tags, `node --check` each.
- **"Working…" hangs** → check `journalctl -u antigravity-web.service`
  for the cid; look for `[SHIM] {cid} … got response` — if missing,
  Vertex 4xx'd; if present, the polling stream isn't emitting a change
  frame (schema drift in `_synthesize_claude_state_frame`).
- **Model routing wrong** → check that `x-user-model` header arrives on
  `SendUserCascadeMessage` (browser DevTools network tab). If missing,
  the injected fetch wrapper didn't install in time — sticky routing by
  cid usually saves us.
- **Conversations missing from sidebar** → curl the summaries endpoint
  and inspect the emitted `trajectoryMetadata.projectId`:
  ```bash
  curl -sN -X POST http://127.0.0.1:8080/exa.language_server_pb.LanguageServerService/JetboxSubscribeToSummaries \
    -H 'Content-Type: application/grpc-web+json' \
    -H "x-codeium-csrf-token: $(grep CSRF_TOKEN /etc/antigravity-web.env | cut -d= -f2)" \
    --data-binary $'\x00\x00\x00\x00\x02{}' | tail -c +6 | python3 -m json.tool | head
  ```

## The repo's docs

Read these in the repo for deeper detail:

- `README.md` — quick start
- `ARCHITECTURE.md` — component diagram
- `docs/claude-shim.md` — how the Vertex shim works (Gemini + Claude)
- `docs/request-flow.md` — byte-level walkthrough of one Claude turn
- `docs/mcp.md` — add-your-own-MCP guide
- `docs/custom-domain.md` — DNS + Google-managed cert setup
- `docs/troubleshooting.md` — known failure modes
