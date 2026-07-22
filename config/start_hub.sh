#!/bin/bash
# Prevent Chromium shared memory crashes on Linux GCE VMs
export CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --headless=new"

# Force Go to use cgo system resolver to prevent local loopback resolution failures on GCE VM network configurations
export GODEBUG=netdns=cgo

# Ensure isolated temp profile directory for language_server
LS_CHROME_DIR="/tmp/ls-chrome-data"
mkdir -p "$LS_CHROME_DIR"

# Clean any stale Chrome locks from LS and user paths to prevent Go launcher timeout aborts
rm -rf "$LS_CHROME_DIR"/*
rm -f "$HOME"/.config/chrome-data/Singleton*
rm -f "$HOME"/.config/chrome-data/DevToolsActivePort.lock

export HOME="${HOME}"
export ANTIGRAVITY_EXECUTABLE_DATA_DIR="$HOME/.gemini/antigravity"
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}"
export ANTIGRAVITY_PROJECT_ID="${GOOGLE_CLOUD_PROJECT}"

BIN_DIR="$HOME/.gemini/antigravity/bin"

# 1. Initialize & Start Knowledge Graph Long-Term Memory (if enabled)
ENABLE_KNOWLEDGE_GRAPH="${ENABLE_KNOWLEDGE_GRAPH:-true}"
KG_PID=""
if [ "$ENABLE_KNOWLEDGE_GRAPH" = "true" ]; then
    echo "Initializing Knowledge Graph Long-Term Memory..."
    python3 "$BIN_DIR/knowledge_graph/init_knowledge_graph.py" 2>/dev/null || true
    python3 "$BIN_DIR/knowledge_graph/kg_mcp_server.py" > /tmp/kg_mcp.log 2>&1 &
    KG_PID=$!
fi

# Start the mock CCPA server to bypass Cloud Code Private API blockers
echo "Starting CCPA Mock Server..."
python3 "$BIN_DIR/ccpa_mock.py" > /tmp/ccpa_mock.log 2>&1 &
MOCK_PID=$!

# Give the mock server a brief moment to initialize and bind to port 8083
sleep 2

# Run the language server with supported flags
echo "Starting language_server natively..."
"$BIN_DIR/language_server" \
    --subclient_type=hub \
    --http_server_port=8081 \
    --model_api_client_type=ccpa \
    --cloud_code_endpoint="http://127.0.0.1:8083" \
    --google_cloud_project="${GOOGLE_CLOUD_PROJECT}" \
    --override_oauth_client_id="${OAUTH_CLIENT_ID}" \
    --override_oauth_client_secret="${OAUTH_CLIENT_SECRET}" \
    -csrf_token="${CSRF_TOKEN}" \
    --override_model_name="gemini-3.5-flash" \
    --local_chrome_headless=true \
    --local_chrome_user_data_dir="$LS_CHROME_DIR" \
    --app_data_dir="antigravity" \
    --gemini_dir=".gemini" \
    -standalone &

LS_PID=$!

# Propagate terminate signals to children gracefully
cleanup() {
    echo "Stopping Antigravity Web Hub processes..."
    kill -TERM "$LS_PID" "$MOCK_PID" $KG_PID 2>/dev/null
    wait "$LS_PID" 2>/dev/null
    wait "$MOCK_PID" 2>/dev/null
    echo "Web Hub stopped successfully."
}
trap cleanup SIGINT SIGTERM EXIT

wait "$LS_PID"
