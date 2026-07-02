#!/bin/bash
# Script to launch the genuine Antigravity Web Hub under systemd, bypass localhost-only binding and Host security checks

# Terminate any stray instances of language_server or proxy.py/socat running on our ports
pkill -f "language_server" || true
pkill -f "proxy.py" || true

export HOME="${HOME}"
export ANTIGRAVITY_EXECUTABLE_DATA_DIR="$HOME/.gemini/antigravity"
export GOOGLE_CLOUD_PROJECT="${GOOGLE_CLOUD_PROJECT}"

BIN_DIR="$HOME/.gemini/antigravity/bin"

# Start the Python reverse proxy in the background on port 8082 for UI/auth mocking
echo "Starting Python proxy.py interceptor..."
python3 "$BIN_DIR/proxy.py" &
PROXY_PID=$!

# Run the language server with supported flags
echo "Starting language_server..."
"$BIN_DIR/language_server" \
    --subclient_type=hub \
    --http_server_port=8081 \
    --model_api_client_type=gemini \
    --cloud_code_endpoint="http://127.0.0.1:8082" \
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
    kill -TERM "$LS_PID" "$PROXY_PID" 2>/dev/null
    wait "$LS_PID" "$PROXY_PID" 2>/dev/null
    echo "Web Hub stopped successfully."
}
trap cleanup SIGINT SIGTERM EXIT

wait "$LS_PID"
