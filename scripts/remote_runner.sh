#!/bin/bash
set -euo pipefail

echo "==> 1. Stopping and killing existing services..."
sudo systemctl stop antigravity-web.service 2>/dev/null || true
pkill -9 -f "language_server" 2>/dev/null || true
pkill -9 -f "ccpa_mock.py" 2>/dev/null || true
rm -rf /tmp/ls-chrome-data /tmp/antigravity-web-hub

echo "==> 2. Unpacking clean deployment archive..."
mkdir -p /tmp/antigravity-web-hub
tar -xzf /tmp/hub.tar.gz -C /tmp/antigravity-web-hub

echo "==> 3. Running scripts/install.sh with sudo -E..."
cd /tmp/antigravity-web-hub
sudo -E bash scripts/install.sh
