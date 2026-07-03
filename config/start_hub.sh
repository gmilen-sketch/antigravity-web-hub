#!/bin/bash
# Script to launch the genuine Antigravity Web Hub under systemd natively

# Terminate any stray instances of language_server, proxy.py, or ccpa_mock.py running on our ports
pkill -f "language_server" || true
pkill -f "proxy.py" || true
pkill -f "ccpa_mock.py" || true

export HOME="${HOME}"
export ANTIGRAVITY_EXECUTABLE_DATA_DIR="$HOME/.gemini/antigravity"
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}"

BIN_DIR="$HOME/.gemini/antigravity/bin"

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
    -csrf_token="${CSRF_TOKEN}" \
    --override_model_name="gemini-3.5-flash" \
    --gemini_dir=".gemini" \
    --app_data_dir="antigravity" \
    -standalone &

LS_PID=$!

# Propagate terminate signals to children gracefully
cleanup() {
    echo "Stopping Antigravity Web Hub processes..."
    kill -TERM "$LS_PID" "$MOCK_PID" 2>/dev/null
    wait "$LS_PID" 2>/dev/null
    wait "$MOCK_PID" 2>/dev/null
    echo "Web Hub stopped successfully."
}
trap cleanup SIGINT SIGTERM EXIT

wait "$LS_PID"
