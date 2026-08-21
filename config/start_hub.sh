#!/bin/bash
export CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --headless=new"
export GODEBUG=netdns=cgo

LS_CHROME_DIR="/tmp/ls-chrome-data"
mkdir -p "$LS_CHROME_DIR"
rm -rf "$LS_CHROME_DIR"/*
rm -f "$HOME"/.config/chrome-data/Singleton*
rm -f "$HOME"/.config/chrome-data/DevToolsActivePort.lock

export HOME="${HOME}"
export ANTIGRAVITY_EXECUTABLE_DATA_DIR="$HOME/.gemini/antigravity"
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT:-second-test-project-393510}"
CSRF_TOKEN="${CSRF_TOKEN:-antigravity_secret_csrf_token_12345}"
export CSRF_TOKEN
export ANTIGRAVITY_PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-second-test-project-393510}"

BIN_DIR="$HOME/.gemini/antigravity/bin"

# 1. Initialize Knowledge Graph Long-Term Memory
python3 "$BIN_DIR/init_knowledge_graph.py" 2>/dev/null || true

# 2. Start CCPA Mock Server (Primary Backend Service)
echo "Starting CCPA Mock Server..."
python3 "$BIN_DIR/ccpa_mock.py" > /tmp/ccpa_mock.log 2>&1 &
MOCK_PID=$!

sleep 2

# 3. Start Language Server natively on port 8081
echo "Starting language_server natively..."
"$BIN_DIR/language_server" \
    -server_port=8081 \
    -cloud_code_endpoint="http://127.0.0.1:8083" \
    -csrf_token="${CSRF_TOKEN}" \
    -app_data_dir="antigravity" \
    -gemini_dir=".gemini" \
    -standalone=true > /tmp/language_server.log 2>&1 &
LS_PID=$!

cleanup() {
    echo "Stopping Antigravity Web Hub processes..."
    kill -TERM "$LS_PID" "$MOCK_PID" 2>/dev/null || true
    wait "$LS_PID" 2>/dev/null || true
    wait "$MOCK_PID" 2>/dev/null || true
    echo "Web Hub stopped successfully."
}
trap cleanup SIGINT SIGTERM EXIT

wait "$MOCK_PID"
