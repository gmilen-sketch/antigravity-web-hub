#!/usr/bin/env bash
# Idempotent installer for Antigravity Web Hub.
# Reads .env from repo root. Run as the *target user* with `sudo -E` so the
# service account below is your normal user, not root.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

CALLER_PROJECT="${GOOGLE_CLOUD_PROJECT:-}"
if [ -z "$CALLER_PROJECT" ]; then
  CALLER_PROJECT=$(curl -sf -m 2 -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/project/project-id 2>/dev/null || true)
fi
CALLER_VM="${VM_NAME:-}"
if [ -z "$CALLER_VM" ]; then
  CALLER_VM=$(curl -sf -m 2 -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name 2>/dev/null || hostname -s 2>/dev/null || true)
fi
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "No .env found — auto-generating .env from .env.example..."
    cp .env.example .env
    sed -i "s/your-gcp-project-id/${CALLER_PROJECT:-my-enterprise-gcp-project}/g" .env
    sed -i "s/your-vm-name/${CALLER_VM:-antigravity-ge-hub}/g" .env
  else
    echo "Missing .env and .env.example" >&2
    exit 1
  fi
fi
if [ -n "$CALLER_PROJECT" ]; then
  sed -i "s/^GOOGLE_CLOUD_PROJECT=.*/GOOGLE_CLOUD_PROJECT=${CALLER_PROJECT}/g" .env
fi
if [ -n "$CALLER_VM" ]; then
  sed -i "s/^VM_NAME=.*/VM_NAME=${CALLER_VM}/g" .env
fi
# Export .env into this shell
set -a; . ./.env; set +a

# Ensure standard system group nobody exists on Debian/Ubuntu GCE VMs
groupadd nobody 2>/dev/null || true

# Ensure standard POSIX loader directory exists on Debian/Ubuntu GCE VMs
mkdir -p /lib64 2>/dev/null || true

RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME=$(getent passwd "$RUN_USER" | cut -d: -f6)

echo "Installing for user=$RUN_USER home=$RUN_HOME project=$GOOGLE_CLOUD_PROJECT"

# Ensure project workspace directory exists with open permissions
mkdir -p /mnt/data/projects/.agents
chmod 0755 /mnt/data /mnt/data/projects /mnt/data/projects/.agents 2>/dev/null || true
chown -R "$RUN_USER:$RUN_USER" /mnt/data 2>/dev/null || true

# ---- 1. Antigravity 2.0 Core Binaries & Web Bundle (Dynamic Official CDN Updater) ----
BIN_DIR="$RUN_HOME/.gemini/antigravity/bin"
mkdir -p "$BIN_DIR" /opt/antigravity/bin "$RUN_HOME/.gemini/config" "$RUN_HOME/.agents" "$RUN_HOME/enterprise-workspace" "$RUN_HOME/workspace" /mnt/data/projects/.agents
chown -R "$RUN_USER:$RUN_USER" "$RUN_HOME/.gemini" "$RUN_HOME/.agents" "$RUN_HOME/enterprise-workspace" "$RUN_HOME/workspace" /mnt/data/projects 2>/dev/null || true

# Dynamically discover the latest official Antigravity 2.0 Hub release from Google Auto-Updater API
DEFAULT_AGY_HUB_VERSION="2.24.0"
DEFAULT_AGY_HUB_EXEC_ID="5780333019398144"
DEFAULT_AGY_CLI_VERSION="1.4.0"
DEFAULT_AGY_CLI_EXEC_ID="5281842794987520"

ANTIGRAVITY_RELEASES_MANIFEST_URL="${ANTIGRAVITY_RELEASES_MANIFEST_URL:-https://antigravity-hub-auto-updater-974169037036.us-central1.run.app/releases}"
AGY_RELEASES_JSON=$(curl -sS --max-time 8 "$ANTIGRAVITY_RELEASES_MANIFEST_URL" 2>/dev/null || true)
RESOLVED_HUB=$(AGY_JSON="$AGY_RELEASES_JSON" python3 -c '
import json, os
try:
    data = json.loads(os.environ.get("AGY_JSON", "") or "[]")
    if isinstance(data, list) and data and data[0].get("version") and data[0].get("execution_id"):
        print(f"{data[0][\"version\"]}|{data[0][\"execution_id\"]}")
except Exception:
    pass
' 2>/dev/null || true)

if [ -n "$RESOLVED_HUB" ]; then
  AGY_HUB_VERSION="${ANTIGRAVITY_HUB_VERSION:-${RESOLVED_HUB%%|*}}"
  AGY_HUB_EXEC_ID="${ANTIGRAVITY_HUB_EXEC_ID:-${RESOLVED_HUB##*|}}"
else
  AGY_HUB_VERSION="${ANTIGRAVITY_HUB_VERSION:-$DEFAULT_AGY_HUB_VERSION}"
  AGY_HUB_EXEC_ID="${ANTIGRAVITY_HUB_EXEC_ID:-$DEFAULT_AGY_HUB_EXEC_ID}"
fi
AGY_CLI_VERSION="${ANTIGRAVITY_CLI_VERSION:-}"
AGY_CLI_EXEC_ID="${ANTIGRAVITY_CLI_EXEC_ID:-}"

if [ -z "$AGY_CLI_VERSION" ] || [ -z "$AGY_CLI_EXEC_ID" ]; then
    CLI_RELEASE_JSON=$(curl -fsSL --max-time 10 "https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/releases" 2>/dev/null || true)
    if [ -n "$CLI_RELEASE_JSON" ]; then
        RESOLVED_CLI_VER=$(python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); r=d.get("releases",[]); print(r[-1].get("version","") if r else "")' <<< "$CLI_RELEASE_JSON" 2>/dev/null || true)
        RESOLVED_CLI_EID=$(python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); r=d.get("releases",[]); print(r[-1].get("execution_id","") if r else "")' <<< "$CLI_RELEASE_JSON" 2>/dev/null || true)
        if [ -n "$RESOLVED_CLI_VER" ] && [ -n "$RESOLVED_CLI_EID" ]; then
            AGY_CLI_VERSION="$RESOLVED_CLI_VER"
            AGY_CLI_EXEC_ID="$RESOLVED_CLI_EID"
        fi
    fi
fi
AGY_CLI_VERSION="${AGY_CLI_VERSION:-$DEFAULT_AGY_CLI_VERSION}"
AGY_CLI_EXEC_ID="${AGY_CLI_EXEC_ID:-$DEFAULT_AGY_CLI_EXEC_ID}"

TARGET_STAMP="${AGY_HUB_VERSION}-${AGY_HUB_EXEC_ID}_cli-${AGY_CLI_VERSION}-${AGY_CLI_EXEC_ID}"
INSTALLED_STAMP=$(cat "$BIN_DIR/.antigravity_version" 2>/dev/null || echo "none")

if [ "${FORCE_BINARY_UPDATE:-false}" = "true" ] || [ "$INSTALLED_STAMP" != "$TARGET_STAMP" ] || [ ! -f "$BIN_DIR/language_server" ] || [ ! -f "$BIN_DIR/antigravity" ]; then
  echo "Updating Antigravity 2.0 Core Components to ${AGY_HUB_VERSION} (${AGY_HUB_EXEC_ID}) & CLI ${AGY_CLI_VERSION}..."
  DL_TMP=$(mktemp -d /tmp/antigravity_2_0_dl.XXXXXX)
  HUB_TARBALL_URL="https://storage.googleapis.com/antigravity-public/antigravity-hub/${AGY_HUB_VERSION}-${AGY_HUB_EXEC_ID}/linux-x64/Antigravity.tar.gz"
  CLI_TARBALL_URL="https://storage.googleapis.com/antigravity-public/antigravity-cli/${AGY_CLI_VERSION}-${AGY_CLI_EXEC_ID}/linux-x64/cli_linux_x64.tar.gz"

  if curl -fSL --max-time 180 -o "$DL_TMP/Antigravity.tar.gz" "$HUB_TARBALL_URL"; then
    tar -xzf "$DL_TMP/Antigravity.tar.gz" -C "$DL_TMP"
    if [ -f "$DL_TMP/Antigravity-x64/resources/bin/language_server" ]; then
      install -o "$RUN_USER" -g "$RUN_USER" -m 0755 "$DL_TMP/Antigravity-x64/resources/bin/language_server" "$BIN_DIR/language_server"
      install -m 0755 "$DL_TMP/Antigravity-x64/resources/bin/language_server" /opt/antigravity/bin/language_server
    elif [ -f "$DL_TMP/Antigravity/resources/app/extensions/antigravity/bin/language_server_linux_x64" ]; then
      install -o "$RUN_USER" -g "$RUN_USER" -m 0755 "$DL_TMP/Antigravity/resources/app/extensions/antigravity/bin/language_server_linux_x64" "$BIN_DIR/language_server"
      install -m 0755 "$DL_TMP/Antigravity/resources/app/extensions/antigravity/bin/language_server_linux_x64" /opt/antigravity/bin/language_server
    fi
    if [ -f "$DL_TMP/Antigravity-x64/resources/bin/webm_encoder" ]; then
      install -o "$RUN_USER" -g "$RUN_USER" -m 0755 "$DL_TMP/Antigravity-x64/resources/bin/webm_encoder" "$BIN_DIR/webm_encoder"
      install -m 0755 "$DL_TMP/Antigravity-x64/resources/bin/webm_encoder" /opt/antigravity/bin/webm_encoder
    fi
    if [ -d "$DL_TMP/Antigravity-x64/resources/app.asar.unpacked/node_modules/chrome-devtools-mcp" ]; then
      rm -rf "$BIN_DIR/chrome-devtools-mcp"
      cp -r "$DL_TMP/Antigravity-x64/resources/app.asar.unpacked/node_modules/chrome-devtools-mcp" "$BIN_DIR/chrome-devtools-mcp"
      chown -R "$RUN_USER:$RUN_USER" "$BIN_DIR/chrome-devtools-mcp"
    fi
    echo "✅ Extracted Antigravity 2.0 Hub (${AGY_HUB_VERSION}) language_server, webm_encoder, and chrome-devtools-mcp."
  elif [ -f "$REPO_ROOT/bin/language_server" ]; then
    echo "Fallback: Installing language_server from repository cache..."
    install -o "$RUN_USER" -g "$RUN_USER" -m 0755 "$REPO_ROOT/bin/language_server" "$BIN_DIR/language_server"
    install -m 0755 "$REPO_ROOT/bin/language_server" /opt/antigravity/bin/language_server
  fi

  if curl -fSL --max-time 90 -o "$DL_TMP/cli_linux_x64.tar.gz" "$CLI_TARBALL_URL"; then
    tar -xzf "$DL_TMP/cli_linux_x64.tar.gz" -C "$DL_TMP"
    if [ -f "$DL_TMP/antigravity" ]; then
      install -o "$RUN_USER" -g "$RUN_USER" -m 0755 "$DL_TMP/antigravity" "$BIN_DIR/antigravity"
      install -m 0755 "$DL_TMP/antigravity" /usr/local/bin/antigravity
      echo "✅ Extracted Antigravity 2.0 Standalone CLI (${AGY_CLI_VERSION}) to /usr/local/bin/antigravity."
    fi
  fi

  # Mirror official Antigravity 2.0 Web UI assets & record cryptographic version manifest
  mkdir -p /var/www/html/web-assets
  for asset in index.html main.js jetbox.css compiled_tailwind.css prism_bundle.js; do
    curl -fsSL --max-time 30 -o "/var/www/html/web-assets/${asset}" \
      "https://antigravity.static.usercontent.goog/web/${AGY_HUB_VERSION}/${asset}" 2>/dev/null || true
  done

  echo "$TARGET_STAMP" > "$BIN_DIR/.antigravity_version"
  chown "$RUN_USER:$RUN_USER" "$BIN_DIR/.antigravity_version"
  rm -rf "$DL_TMP"
else
  echo "Antigravity 2.0 Core Components already up-to-date ($INSTALLED_STAMP)."
fi

# Record runtime version & SHA-256 manifest for /api/version verification
python3 - <<PYEOF
import hashlib, json, os, subprocess

bin_dir = "$BIN_DIR"
def sha256_file(path):
    if not os.path.isfile(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

ls_path = os.path.join(bin_dir, "language_server")
cli_path = os.path.join(bin_dir, "antigravity")
webm_path = os.path.join(bin_dir, "webm_encoder")

ls_stamp = ""
if os.path.isfile(ls_path):
    try:
        ls_stamp = subprocess.check_output([ls_path, "-stamp"], text=True, stderr=subprocess.STDOUT, timeout=5).strip()
    except Exception:
        pass

cli_ver = ""
if os.path.isfile(cli_path):
    try:
        cli_ver = subprocess.check_output([cli_path, "--version"], text=True, stderr=subprocess.STDOUT, timeout=5).strip()
    except Exception:
        pass

manifest = {
    "hub_version": "3.5.0",
    "antigravity_core_version": "$AGY_HUB_VERSION",
    "antigravity_execution_id": "$AGY_HUB_EXEC_ID",
    "antigravity_cli_version": cli_ver or "$AGY_CLI_VERSION",
    "antigravity_cli_execution_id": "$AGY_CLI_EXEC_ID",
    "language_server_stamp": ls_stamp,
    "language_server_bytes": os.path.getsize(ls_path) if os.path.isfile(ls_path) else 0,
    "language_server_sha256": sha256_file(ls_path),
    "webm_encoder_present": os.path.isfile(webm_path),
    "webm_encoder_sha256": sha256_file(webm_path),
    "antigravity_cli_present": os.path.isfile(cli_path),
    "antigravity_cli_sha256": sha256_file(cli_path),
    "chrome_devtools_mcp_present": os.path.isdir(os.path.join(bin_dir, "chrome-devtools-mcp")),
    "web_assets_mirrored": os.path.isfile("/var/www/html/web-assets/main.js"),
}
for dest in (os.path.join(bin_dir, "antigravity-release.json"), "/var/www/html/antigravity-release.json"):
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w") as out:
            json.dump(manifest, out, indent=2)
    except Exception:
        pass
PYEOF

# ---- 2. System dependencies & Python deps -----------------------------------
echo "Installing system package dependencies (python3-pip, python3-venv, nginx, nodejs, npm, chromium, unzip, psmisc)..."
apt-get update -qq && apt-get install -y -qq python3-pip python3-venv nginx nodejs npm chromium curl ca-certificates unzip psmisc
(cd "$REPO_ROOT" && sudo -u "$RUN_USER" npm install ws --no-save --silent 2>/dev/null || true)

echo "Installing Python FastMCP & AI dependencies..."
pip install --break-system-packages -r requirements.txt || true

# ---- 3. Install Source Modules into Antigravity SDK bin dir -----------------
chown -R "$RUN_USER:$RUN_USER" "$RUN_HOME/.gemini"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/ccpa_mock.py         "$BIN_DIR/ccpa_mock.py"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/ensure_wal.py        "$BIN_DIR/ensure_wal.py"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/mcp_deep_research.py "$BIN_DIR/mcp_deep_research.py"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 config/start_hub.sh      "$BIN_DIR/start_hub.sh"

# Install Knowledge Graph Long-Term Memory module files
if [ -d "src/knowledge_graph" ]; then
  echo "Installing Knowledge Graph Long-Term Memory module..."
  mkdir -p "$BIN_DIR/knowledge_graph"
  cp -r src/knowledge_graph/* "$BIN_DIR/knowledge_graph/"
  chown -R "$RUN_USER:$RUN_USER" "$BIN_DIR/knowledge_graph"
  chmod +x "$BIN_DIR/knowledge_graph"/*.py 2>/dev/null || true
  sudo -u "$RUN_USER" python3 "$BIN_DIR/knowledge_graph/init_knowledge_graph.py" || true
fi

# Install Autonomy Engine module files
if [ -d "src/autonomy_engine" ]; then
  echo "Installing Autonomy Engine FastMCP module..."
  mkdir -p "$BIN_DIR/autonomy_engine"
  cp -r src/autonomy_engine/* "$BIN_DIR/autonomy_engine/"
  chown -R "$RUN_USER:$RUN_USER" "$BIN_DIR/autonomy_engine"
  chmod +x "$BIN_DIR/autonomy_engine"/*.py 2>/dev/null || true
fi

# Install Lifecycle Hooks module files (PreInvocation, PreToolUse Sentinel & Stop Gate)
if [ -d "src/hooks" ]; then
  echo "Installing Lifecycle Hooks (PreInvocation KG Grounding, PreToolUse Sentinel & 2-Stage Black-Hat Stop Gate)..."
  mkdir -p "$BIN_DIR/hooks/rules"
  cp -r src/hooks/* "$BIN_DIR/hooks/"
  chown -R "$RUN_USER:$RUN_USER" "$BIN_DIR/hooks"
  chmod +x "$BIN_DIR/hooks"/*.py 2>/dev/null || true
fi

# Install Open Knowledge Format (OKF v0.2) kb/ bundle and Diagram Renderer v15.2
if [ -d "kb" ]; then
  echo "Installing Open Knowledge Format (OKF v0.2) kb/ bundle..."
  mkdir -p "$RUN_HOME/kb" "$BIN_DIR/kb"
  cp -r kb/* "$RUN_HOME/kb/"
  cp -r kb/* "$BIN_DIR/kb/"
  chown -R "$RUN_USER:$RUN_USER" "$RUN_HOME/kb" "$BIN_DIR/kb"
  sudo -u "$RUN_USER" python3 "$BIN_DIR/knowledge_graph/okf_knowledge_compiler.py" --kb-root "$RUN_HOME/kb" || true
fi

if [ -d "src/diagram_renderer" ]; then
  echo "Installing Diagram Renderer v15.2 module..."
  mkdir -p "$BIN_DIR/diagram_renderer"
  cp -r src/diagram_renderer/* "$BIN_DIR/diagram_renderer/"
  chown -R "$RUN_USER:$RUN_USER" "$BIN_DIR/diagram_renderer"
  chmod +x "$BIN_DIR/diagram_renderer"/*.py 2>/dev/null || true
fi

if [ -d "src/mcp_servers" ]; then
  echo "Installing Clean-Room Open-Source MCP Adapters (browser_cdp, cloud_telemetry, workspace_docs)..."
  mkdir -p "$BIN_DIR/mcp_servers"
  cp -r src/mcp_servers/* "$BIN_DIR/mcp_servers/"
  chown -R "$RUN_USER:$RUN_USER" "$BIN_DIR/mcp_servers"
  chmod +x "$BIN_DIR/mcp_servers"/*.py 2>/dev/null || true
fi

# Install Google Workspace MCP module
if [ -d "src/mcp_google_workspace" ]; then
  echo "Installing Google Workspace MCP module..."
  mkdir -p "$BIN_DIR/mcp_google_workspace"
  cp -r src/mcp_google_workspace/* "$BIN_DIR/mcp_google_workspace/"
  chown -R "$RUN_USER:$RUN_USER" "$BIN_DIR/mcp_google_workspace"
  if command -v npm >/dev/null 2>&1; then
    (cd "$BIN_DIR/mcp_google_workspace" && sudo -u "$RUN_USER" npm install --silent || true)
  fi
fi

# ---- 4. Configure MCP Servers (mcp_config.json) & Lifecycle Hooks (hooks.json) ----
echo "Configuring mcp_config.json and hooks.json across all search paths..."
sudo -u "$RUN_USER" python3 -c "
import json, os
bin_dir = '$BIN_DIR'
home = '$RUN_HOME'

mcp_cfg = {
  'mcpServers': {
    'knowledge_graph': {
      'command': 'python3',
      'args': [f'{bin_dir}/knowledge_graph/kg_mcp_server.py']
    },
    'autonomy_engine': {
      'command': 'python3',
      'args': [f'{bin_dir}/autonomy_engine/mcp_autonomy_hub.py']
    },
    'diagram_renderer': {
      'command': 'python3',
      'args': [f'{bin_dir}/diagram_renderer/diagram_mcp_server.py']
    },
    'browser_cdp': {
      'command': 'python3',
      'args': [f'{bin_dir}/mcp_servers/browser_cdp_mcp.py']
    },
    'cloud_telemetry': {
      'command': 'python3',
      'args': [f'{bin_dir}/mcp_servers/cloud_telemetry_mcp.py']
    },
    'workspace_docs': {
      'command': 'python3',
      'args': [f'{bin_dir}/mcp_servers/workspace_docs_mcp.py']
    },
    'deep_research': {
      'command': 'python3',
      'args': [f'{bin_dir}/mcp_deep_research.py', '--transport', 'stdio']
    },
    'google_workspace': {
      'command': 'node',
      'args': [f'{bin_dir}/mcp_google_workspace/index.js']
    }
  }
}

hooks_cfg = {
  'knowledge-graph-grounding': {
    'enabled': True,
    'PreInvocation': [
      {
        'type': 'command',
        'command': f'python3 {bin_dir}/hooks/kg_pre_invocation_hook.py',
        'timeout': 5
      }
    ]
  },
  'sentinel-pre-tool-gate': {
    'enabled': True,
    'PreToolUse': [
      {
        'type': 'command',
        'command': f'python3 {bin_dir}/hooks/sentinel_dispatch.py',
        'timeout': 5
      }
    ]
  },
  'black-hat-completion-gate': {
    'enabled': True,
    'Stop': [
      {
        'type': 'command',
        'command': f'python3 {bin_dir}/hooks/agent_stop_black_hat_gate.py',
        'timeout': 15
      }
    ]
  }
}

paths = [
  f'{home}/.gemini/config/mcp_config.json',
  f'{home}/.gemini/config/mcp.json',
  f'{home}/.gemini/antigravity/mcp_config.json',
  f'{home}/.gemini/antigravity/mcp.json',
  f'{home}/.gemini/mcp_config.json',
  f'{home}/.gemini/mcp.json',
  f'{home}/.agents/mcp_config.json',
  f'{home}/.agents/mcp.json',
  f'/mnt/data/projects/.agents/mcp_config.json',
  f'/mnt/data/projects/.agents/mcp.json'
]

for p in paths:
  try:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
      json.dump(mcp_cfg, f, indent=2)
  except Exception as e:
    pass

hook_paths = [
  f'{home}/.gemini/config/hooks.json',
  f'{home}/.gemini/antigravity/hooks.json'
]

for hp in hook_paths:
  try:
    os.makedirs(os.path.dirname(hp), exist_ok=True)
    with open(hp, 'w') as f:
      json.dump(hooks_cfg, f, indent=2)
  except Exception as e:
    pass
"

# ---- 5. Install Community Skills and Custom Subagents (black-hat-critic) ----
if [ -d "skills" ]; then
  echo "Installing Community Skills catalog..."
  for skill_path in skills/*; do
    if [ -d "$skill_path" ]; then
      skill_name=$(basename "$skill_path")
      for dest in "$RUN_HOME/.gemini/config/skills/$skill_name" \
                  "$RUN_HOME/.gemini/antigravity/skills/$skill_name" \
                  "$RUN_HOME/.gemini/skills/$skill_name" \
                  "$RUN_HOME/.agents/skills/$skill_name" \
                  "/mnt/data/projects/.agents/skills/$skill_name"; do
        mkdir -p "$(dirname "$dest")"
        rm -rf "$dest"
        cp -r "$skill_path" "$dest"
        chown -R "$RUN_USER:$RUN_USER" "$dest" 2>/dev/null || true
      done
    fi
  done
fi

if [ -d "agents" ]; then
  echo "Installing Custom Subagents (black-hat-critic)..."
  for agent_path in agents/*; do
    if [ -d "$agent_path" ]; then
      agent_name=$(basename "$agent_path")
      for dest in "$RUN_HOME/.gemini/config/agents/$agent_name" \
                  "$RUN_HOME/.gemini/antigravity/agents/$agent_name" \
                  "$RUN_HOME/.gemini/agents/$agent_name" \
                  "$RUN_HOME/.agents/agents/$agent_name" \
                  "/mnt/data/projects/.agents/agents/$agent_name"; do
        mkdir -p "$(dirname "$dest")"
        rm -rf "$dest"
        cp -r "$agent_path" "$dest"
        chown -R "$RUN_USER:$RUN_USER" "$dest" 2>/dev/null || true
      done
    fi
  done
fi

# ---- 6. Bypass Onboarding Screen with antigravity_state.pbtxt (Preserve Existing State) ----
echo "Checking onboarding state..."
if [ -f "config/antigravity_state.pbtxt" ]; then
  if [ ! -f "$RUN_HOME/.gemini/antigravity/antigravity_state.pbtxt" ]; then
    cp config/antigravity_state.pbtxt "$RUN_HOME/.gemini/antigravity/antigravity_state.pbtxt"
    chown "$RUN_USER:$RUN_USER" "$RUN_HOME/.gemini/antigravity/antigravity_state.pbtxt"
  fi
  if [ ! -f "$BIN_DIR/antigravity_state.pbtxt" ]; then
    cp config/antigravity_state.pbtxt "$BIN_DIR/antigravity_state.pbtxt"
    chown "$RUN_USER:$RUN_USER" "$BIN_DIR/antigravity_state.pbtxt"
  fi
fi

# ---- 7. Configure Nginx Reverse Proxy ----
if command -v nginx >/dev/null 2>&1; then
  echo "Configuring Nginx Reverse Proxy (serving embedded UI from language_server :8081)..."
  mkdir -p /var/www/html
  install -m 0644 src/bootstrap.js /var/www/html/bootstrap.js
  install -m 0644 config/nginx.conf /etc/nginx/conf.d/antigravity-web.conf
  rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default 2>/dev/null || true
  systemctl enable nginx 2>/dev/null || true
  nginx -t && systemctl restart nginx
fi

# ---- 8. Configure Nightly Dreaming & SQLite WAL Maintenance Crontabs ----
echo "Configuring automatic SQLite WAL and Nightly Dreaming (23:50 UTC) crontab..."
(sudo -u "$RUN_USER" crontab -l 2>/dev/null | grep -v "dreaming_engine.py" | grep -v "ensure_wal.py" || true; \
 echo "* * * * * python3 $BIN_DIR/ensure_wal.py > /dev/null 2>&1"; \
 echo "50 23 * * * python3 $BIN_DIR/knowledge_graph/dreaming_engine.py --hours 24 >> /tmp/dreaming.log 2>&1") | sudo -u "$RUN_USER" crontab -

# ---- 9. Systemd Service Configuration ----
killall -9 language_server webm_encoder 2>/dev/null || true
fuser -k 8081/tcp 8083/tcp 2>/dev/null || true
sed "s/REPLACE_USER/$RUN_USER/g" config/antigravity-web.service \
  > /etc/systemd/system/antigravity-web.service
install -m 0644 .env /etc/antigravity-web.env 2>/dev/null || true

systemctl daemon-reload
systemctl enable antigravity-web.service
systemctl restart antigravity-web.service

for _i in $(seq 1 35); do
  if curl -sf http://127.0.0.1:8080/healthz >/dev/null 2>&1 \
     && curl -sf http://127.0.0.1:8080/api/version >/dev/null 2>&1 \
     && curl -sf http://127.0.0.1:8080/ | grep -q 'id="root"'; then
    break
  fi
  sleep 1
done

echo
echo "✅ Antigravity Web Hub Installation Complete."
echo "Tail logs with: journalctl -u antigravity-web.service -f"
