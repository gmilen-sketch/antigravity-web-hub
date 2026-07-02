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

RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME=$(getent passwd "$RUN_USER" | cut -d: -f6)

echo "Installing for user=$RUN_USER home=$RUN_HOME project=$GOOGLE_CLOUD_PROJECT"

# ---- 1. Antigravity CLI (Google's public installer) ---------------------
if [ ! -x "$RUN_HOME/.gemini/antigravity/bin/language_server" ]; then
  echo "Installing Antigravity CLI (Google's public installer)…"
  sudo -u "$RUN_USER" bash -c \
    'curl -sSL https://antigravity.google/install.sh | sh' || {
      echo "Antigravity CLI install failed — visit https://antigravity.google/ to download manually" >&2
      exit 1
    }
else
  echo "Antigravity CLI already installed (skipping)."
fi

# ---- 2. Python deps ------------------------------------------------------
echo "Installing Python deps…"
sudo -u "$RUN_USER" pip install --user --break-system-packages -r requirements.txt

# ---- 3. Node MCP stub deps ----------------------------------------------
if command -v npm >/dev/null 2>&1; then
  echo "Installing Node MCP stub deps…"
  sudo -u "$RUN_USER" bash -c "cd $REPO_ROOT/src/mcp_node_stub && npm install --silent"
else
  echo "npm not found — skipping Node MCP stub (optional)."
fi

# ---- 4. Optional data-disk formatting -----------------------------------
if [ -b /dev/sdb ] && ! blkid /dev/sdb >/dev/null 2>&1 && [ ! -d /mnt/data ]; then
  read -r -p "Format empty /dev/sdb ext4 and mount at /mnt/data? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
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
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/proxy.py             "$BIN_DIR/proxy.py"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 src/mcp_deep_research.py "$BIN_DIR/mcp_deep_research.py"
install -o "$RUN_USER" -g "$RUN_USER" -m 0755 config/start_hub.sh      "$BIN_DIR/start_hub.sh"

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
install -m 0640 .env /etc/antigravity-web.env

systemctl daemon-reload
systemctl enable antigravity-web.service
systemctl restart antigravity-web.service

echo
echo "Done. Tail logs with:"
echo "  journalctl -u antigravity-web.service -f"
echo
echo "Visit  https://$PUBLIC_HOSTNAME/"
