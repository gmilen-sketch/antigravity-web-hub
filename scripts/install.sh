#!/usr/bin/env bash
# Idempotent installer for Antigravity Web Hub.
# Reads .env from repo root. Run as the *target user* with `sudo -E` so the
# service account below is your normal user, not root.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env ]; then
  echo "Missing .env — copy .env.example to .env and fill it in first." >&2
  exit 1
fi
# Export .env into this shell
set -a; . ./.env; set +a

# Ensure system group nobody exists for init_google initialization on Debian GCE VMs
groupadd nobody 2>/dev/null || true

RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME=$(getent passwd "$RUN_USER" | cut -d: -f6)

echo "Installing for user=$RUN_USER home=$RUN_HOME project=$GOOGLE_CLOUD_PROJECT"

# Ensure project workspace directory exists with open permissions
mkdir -p /mnt/data/projects
chmod -R 777 /mnt/data
chown -R "$RUN_USER:$RUN_USER" /mnt/data 2>/dev/null || true

# ---- 1. Antigravity language_server binary ---------------------
BIN_DIR="$RUN_HOME/.gemini/antigravity/bin"
mkdir -p "$BIN_DIR"
chown -R "$RUN_USER:$RUN_USER" "$RUN_HOME/.gemini"

if [ -f "$REPO_ROOT/bin/language_server" ]; then
  echo "Installing native Go language_server from repository package…"
  rm -f "$BIN_DIR/language_server"
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 "$REPO_ROOT/bin/language_server" "$BIN_DIR/language_server"
elif [ ! -x "$BIN_DIR/language_server" ]; then
  if [ -x "$RUN_HOME/.local/bin/agy" ]; then
    ln -sf "$RUN_HOME/.local/bin/agy" "$BIN_DIR/language_server"
  else
    echo "Installing Antigravity CLI (Google's public installer)…"
    sudo -u "$RUN_USER" bash -c \
      'curl -fsSL https://antigravity.google/cli/install.sh | bash' || true
    if [ -x "$RUN_HOME/.local/bin/agy" ]; then
      ln -sf "$RUN_HOME/.local/bin/agy" "$BIN_DIR/language_server"
    fi
  fi
fi

# Check Application Default Credentials (ADC)
if [ ! -f "$RUN_HOME/.config/gcloud/application_default_credentials.json" ]; then
  echo "WARNING: Application Default Credentials (ADC) missing at $RUN_HOME/.config/gcloud/application_default_credentials.json"
  echo "Please run 'gcloud auth application-default login' to authenticate with Vertex AI."
fi

# ---- 2. System dependencies & Python deps -----------------------------------
echo "Installing system package dependencies (python3-pip, python3-venv, nginx, nodejs, npm)…"
apt-get update -qq && apt-get install -y -qq python3-pip python3-venv nginx nodejs npm curl ca-certificates

echo "Installing Python deps…"
sudo -u "$RUN_USER" pip install --user --break-system-packages -r requirements.txt

# ---- 3. Node MCP stub deps ----------------------------------------------
if command -v npm >/dev/null 2>&1; then
  echo "Installing Node MCP stub deps…"
  sudo -u "$RUN_USER" bash -c "cd $REPO_ROOT/src/mcp_node_stub && npm install --silent"
else
  echo "npm not found — skipping Node MCP stub (optional)."
fi

# ---- 4. Data-disk formatting -----------------------------------
if [ -b /dev/sdb ] && ! blkid /dev/sdb >/dev/null 2>&1 && [ ! -d /mnt/data ]; then
  ans="y"
  if [ -t 0 ]; then
    read -r -p "Format empty /dev/sdb ext4 and mount at /mnt/data? [y/N] " user_ans
    ans="${user_ans:-n}"
  fi
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    echo "Formatting empty /dev/sdb ext4 and mounting at /mnt/data…"
    mkfs.ext4 -F -L antigravity-data /dev/sdb
    mkdir -p /mnt/data
    UUID=$(blkid -s UUID -o value /dev/sdb)
    grep -q "$UUID" /etc/fstab || \
      echo "UUID=$UUID /mnt/data ext4 defaults,nofail 0 2" >> /etc/fstab
    mount /mnt/data
    chown -R "$RUN_USER:$RUN_USER" /mnt/data
    mkdir -p /mnt/data/antigravity/claude_cascades
    chown -R "$RUN_USER:$RUN_USER" /mnt/data/antigravity
  fi
fi

# ---- 5. Install source into the Antigravity SDK bin dir -----------------
BIN_DIR="$RUN_HOME/.gemini/antigravity/bin"
mkdir -p "$BIN_DIR/knowledge_graph"
chown -R "$RUN_USER:$RUN_USER" "$RUN_HOME/.gemini"
rm -f "$BIN_DIR/proxy.py"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/ccpa_mock.py         "$BIN_DIR/ccpa_mock.py"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/ensure_wal.py        "$BIN_DIR/ensure_wal.py"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/mcp_deep_research.py "$BIN_DIR/mcp_deep_research.py"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 config/start_hub.sh      "$BIN_DIR/start_hub.sh"

# Install Knowledge Graph Long-Term Memory module files
if [ -d "src/knowledge_graph" ]; then
  echo "Installing Knowledge Graph Long-Term Memory module..."
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/knowledge_graph/kg_engine.py          "$BIN_DIR/knowledge_graph/kg_engine.py"
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/knowledge_graph/init_knowledge_graph.py "$BIN_DIR/knowledge_graph/init_knowledge_graph.py"
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/knowledge_graph/kg_mcp_server.py      "$BIN_DIR/knowledge_graph/kg_mcp_server.py"
  sudo -u "$RUN_USER" python3 "$BIN_DIR/knowledge_graph/init_knowledge_graph.py" || true
fi

# Install Diagram Renderer module
if [ -d "src/diagram_renderer" ]; then
  echo "Installing Offline Diagram Renderer module..."
  mkdir -p "$BIN_DIR/diagram_renderer"
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/diagram_renderer/render_mermaid.py     "$BIN_DIR/diagram_renderer/render_mermaid.py"
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/diagram_renderer/diagram_mcp_server.py "$BIN_DIR/diagram_renderer/diagram_mcp_server.py"
fi

# Install Six Thinking Hats Reasoning module
if [ -d "src/six_hats_evaluator" ]; then
  echo "Installing Six Thinking Hats Evaluator module..."
  mkdir -p "$BIN_DIR/six_hats_evaluator"
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/six_hats_evaluator/six_hats.py           "$BIN_DIR/six_hats_evaluator/six_hats.py"
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/six_hats_evaluator/six_hats_mcp_server.py "$BIN_DIR/six_hats_evaluator/six_hats_mcp_server.py"
fi

# Install Playwright Web Scraper module
if [ -d "src/playwright_scraper" ]; then
  echo "Installing Playwright Headless Web Scraper module..."
  mkdir -p "$BIN_DIR/playwright_scraper"
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/playwright_scraper/playwright_scraper.py    "$BIN_DIR/playwright_scraper/playwright_scraper.py"
  install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/playwright_scraper/playwright_mcp_server.py "$BIN_DIR/playwright_scraper/playwright_mcp_server.py"
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

# ---- 5a. Configure installed MCP servers in Antigravity configuration ----
echo "Registering installed MCP servers in Antigravity configuration..."
sudo -u "$RUN_USER" python3 -c "
import json, os
bin_dir = '$BIN_DIR'
home = '$RUN_HOME'

mcp_cfg = {
  'mcpServers': {
    'deep_research': {
      'command': 'python3',
      'args': [f'{bin_dir}/mcp_deep_research.py', '--transport', 'stdio'],
      'env': {},
      'disabled': False
    },
    'knowledge_graph': {
      'command': 'python3',
      'args': [f'{bin_dir}/knowledge_graph/kg_mcp_server.py'],
      'env': {},
      'disabled': False
    },
    'diagram_renderer': {
      'command': 'python3',
      'args': [f'{bin_dir}/diagram_renderer/diagram_mcp_server.py'],
      'env': {},
      'disabled': False
    },
    'six_hats_evaluator': {
      'command': 'python3',
      'args': [f'{bin_dir}/six_hats_evaluator/six_hats_mcp_server.py'],
      'env': {},
      'disabled': False
    },
    'playwright_scraper': {
      'command': 'python3',
      'args': [f'{bin_dir}/playwright_scraper/playwright_mcp_server.py'],
      'env': {},
      'disabled': False
    },
    'google_workspace': {
      'command': 'node',
      'args': [f'{bin_dir}/mcp_google_workspace/index.js'],
      'env': {},
      'disabled': False
    }
  }
}

paths = [
  f'{home}/.gemini/config/mcp_config.json',
  f'{home}/.gemini/antigravity/mcp_config.json',
  f'{home}/.gemini/mcp_config.json',
  f'{home}/.gemini/config/mcp_servers.json',
]

for p in paths:
  os.makedirs(os.path.dirname(p), exist_ok=True)
  with open(p, 'w') as f:
    json.dump(mcp_cfg, f, indent=2)
" || true

# ---- 5b. Configure automatic WAL database optimization cron job ----------
echo "Configuring automatic SQLite WAL database optimizer cron job..."
(sudo -u "$RUN_USER" crontab -l 2>/dev/null | grep -v "ensure_wal.py" || true; echo "* * * * * $BIN_DIR/ensure_wal.py > /dev/null 2>&1") | sudo -u "$RUN_USER" crontab -


# ---- 6. nginx site -------------------------------------------------------
if command -v nginx >/dev/null 2>&1; then
  install -m 0644 config/nginx.conf /etc/nginx/sites-available/antigravity-web
  ln -sf /etc/nginx/sites-available/antigravity-web /etc/nginx/sites-enabled/antigravity-web
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
else
  echo "nginx not installed — run 'apt install nginx' and re-run this script."
fi

# ---- 7. systemd unit + env file -----------------------------------------
sed "s/REPLACE_USER/$RUN_USER/g" config/antigravity-web.service \
  > /etc/systemd/system/antigravity-web.service
install -m 0644 .env /etc/antigravity-web.env

systemctl daemon-reload
systemctl enable antigravity-web.service
systemctl restart antigravity-web.service

echo
echo "Done. Tail logs with:"
echo "  journalctl -u antigravity-web.service -f"
echo
echo "Visit  https://${PUBLIC_HOSTNAME:-<your-lb-ip>.nip.io}/"
