#!/usr/bin/env bash
# Idempotent installer for Antigravity Web Hub.
# Reads .env from repo root. Run as the *target user* with `sudo -E` so the
# service account below is your normal user, not root.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "No .env found — auto-generating .env from .env.example..."
    cp .env.example .env
    sed -i "s/your-gcp-project-id/${GOOGLE_CLOUD_PROJECT:-second-test-project-393510}/g" .env
    sed -i "s/your-vm-name/${VM_NAME:-antigravity-ge-hub}/g" .env
  else
    echo "Missing .env and .env.example" >&2
    exit 1
  fi
fi
# Export .env into this shell
set -a; . ./.env; set +a

# Ensure system group nobody exists for init_google initialization on Debian GCE VMs
groupadd nobody 2>/dev/null || true

RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME=$(getent passwd "$RUN_USER" | cut -d: -f6)

echo "Installing for user=$RUN_USER home=$RUN_HOME project=$GOOGLE_CLOUD_PROJECT"

# Ensure project workspace directory exists with open permissions
mkdir -p /mnt/data/projects/.agents
chmod -R 777 /mnt/data 2>/dev/null || true
chown -R "$RUN_USER:$RUN_USER" /mnt/data 2>/dev/null || true

# ---- 1. Antigravity language_server binary ---------------------
BIN_DIR="$RUN_HOME/.gemini/antigravity/bin"
mkdir -p "$BIN_DIR" "$RUN_HOME/.gemini/config" "$RUN_HOME/.agents" /mnt/data/projects/.agents
chown -R "$RUN_USER:$RUN_USER" "$RUN_HOME/.gemini" "$RUN_HOME/.agents" /mnt/data/projects 2>/dev/null || true

if [ -f "$REPO_ROOT/bin/language_server" ]; then
  echo "Installing language_server from repository bin/..."
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 "$REPO_ROOT/bin/language_server" "$BIN_DIR/language_server"
elif [ -f "$BIN_DIR/language_server" ]; then
  echo "Existing language_server found at $BIN_DIR/language_server."
else
  echo "Downloading official Antigravity binary from Google CDN..."
  mkdir -p /tmp/antigravity_dl
  curl -s -o /tmp/antigravity_dl/Antigravity.tar.gz https://edgedl.me.gvt1.com/edgedl/release2/j0qc3/antigravity/stable/1.16.5-6703236727046144/linux-x64/Antigravity.tar.gz
  tar -xzf /tmp/antigravity_dl/Antigravity.tar.gz -C /tmp/antigravity_dl Antigravity/resources/app/extensions/antigravity/bin/language_server_linux_x64
  mv /tmp/antigravity_dl/Antigravity/resources/app/extensions/antigravity/bin/language_server_linux_x64 "$BIN_DIR/language_server"
  chmod 0755 "$BIN_DIR/language_server"
  rm -rf /tmp/antigravity_dl
  echo "Extracted language_server binary to $BIN_DIR/language_server"
fi

# ---- 2. System dependencies & Python deps -----------------------------------
echo "Installing system package dependencies (python3-pip, python3-venv, nginx, nodejs, npm)..."
apt-get update -qq && apt-get install -y -qq python3-pip python3-venv nginx nodejs npm curl ca-certificates

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

# ---- 4. Configure MCP Servers (mcp_config.json) across all discovery search paths ----
echo "Configuring mcp_config.json across all search paths..."
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
"

# ---- 5. Install Community Skills and configure skills.json ----
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

# ---- 6. Bypass Onboarding Screen with jetski_state.pbtxt ----
echo "Writing onboarding bypass state..."
if [ -f "config/jetski_state.pbtxt" ]; then
  cp config/jetski_state.pbtxt "$RUN_HOME/.gemini/antigravity/jetski_state.pbtxt"
  cp config/jetski_state.pbtxt "$BIN_DIR/jetski_state.pbtxt"
  chown "$RUN_USER:$RUN_USER" "$RUN_HOME/.gemini/antigravity/jetski_state.pbtxt" "$BIN_DIR/jetski_state.pbtxt"
fi

# ---- 7. Configure Nginx Reverse Proxy ----
if command -v nginx >/dev/null 2>&1; then
  install -m 0644 config/nginx.conf /etc/nginx/sites-available/default
  nginx -t && systemctl reload nginx || systemctl restart nginx
fi

# ---- 8. Configure Nightly Dreaming & SQLite WAL Maintenance Crontabs ----
echo "Configuring automatic SQLite WAL and Nightly Dreaming (23:50 UTC) crontab..."
(sudo -u "$RUN_USER" crontab -l 2>/dev/null | grep -v "dreaming_engine.py" | grep -v "ensure_wal.py" || true; \
 echo "* * * * * python3 $BIN_DIR/ensure_wal.py > /dev/null 2>&1"; \
 echo "50 23 * * * python3 $BIN_DIR/knowledge_graph/dreaming_engine.py --hours 24 >> /tmp/dreaming.log 2>&1") | sudo -u "$RUN_USER" crontab -

# ---- 9. Systemd Service Configuration ----
sed "s/REPLACE_USER/$RUN_USER/g" config/antigravity-web.service \
  > /etc/systemd/system/antigravity-web.service
install -m 0644 .env /etc/antigravity-web.env 2>/dev/null || true

systemctl daemon-reload
systemctl enable antigravity-web.service
systemctl restart antigravity-web.service

echo
echo "✅ Antigravity Web Hub Installation Complete."
echo "Tail logs with: journalctl -u antigravity-web.service -f"
