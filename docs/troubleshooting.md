# Troubleshooting

Known failure modes and their resolutions in the native proxy-less CCPA-mock architecture.

## 1. Browser shows "Working…" spinner forever with no model response

### Cause
This occurs if the Go `language_server` (port `8081`) or the `ccpa_mock.py` sidecar (port `8083`) did not receive, process, or successfully stream the model generation from Vertex AI.

### Diagnostic Steps
1. **Check Service Logs**: Check the unified systemd unit status and its logs:
   ```bash
   sudo systemctl status antigravity-web.service --no-pager
   journalctl -u antigravity-web.service -f --since "5 min ago"
   ```
2. **Inspect Mock Logs**: Check if the mock sidecar is experiencing errors forwarding to Vertex AI:
   ```bash
   tail -n 100 /tmp/ccpa_mock.log
   ```
3. **Verify Vertex AI Connection**: Test if the sidecar can retrieve a Google Cloud Access Token and reach Vertex AI using Google Application Default Credentials (ADC):
   ```bash
   gcloud auth application-default print-access-token
   ```
   If credentials are missing or expired, re-run:
   ```bash
   gcloud auth application-default login
   ```

---

## 2. Startup Aborts / "Address already in use" (Ports 8081 / 8083)

### Cause
A previous instance of the Go `language_server` or the Python `ccpa_mock.py` process did not shut down cleanly and is still bound to port `8081` or `8083`.

### Diagnostic Steps
1. Find what process is holding the ports:
   ```bash
   sudo lsof -i :8081 -i :8083
   ```
2. Kill the stale processes:
   ```bash
   sudo pkill -9 -f language_server || true
   sudo pkill -9 -f ccpa_mock.py || true
   ```
3. Restart the service:
   ```bash
   sudo systemctl restart antigravity-web.service
   ```

---

## 3. Chrome Launcher Timeouts / SingletonLock Blocks

### Cause
The Go `language_server` spawns an internal Chromium process for web-rendering tasks or browser-based tools. If Chromium crashes or gets interrupted, a stale `SingletonLock` file is left in the user-profile directory, causing future starts of Chrome to hang forever.

### Diagnostic Steps
1. **Kill Zombie Chrome Processes**:
   ```bash
   sudo pkill -9 -f chrome || true
   ```
2. **Remove Stale Locks**:
   ```bash
   # Clean language_server profile
   rm -rf /tmp/ls-chrome-data/*
   
   # Clean general user profile
   rm -f ~/.config/chrome-data/Singleton*
   rm -f ~/.config/chrome-data/DevToolsActivePort.lock
   ```
3. **Restart the Web Hub Service**:
   ```bash
   sudo systemctl restart antigravity-web.service
   ```

---

## 4. Local loopback / connection errors on GCE VMs

### Cause
By default, Go's pure-Go DNS resolver can sometimes experience address resolution delays or failures for `127.0.0.1` or `localhost` within Google Compute Engine (GCE) VM network environments.

### Fix
Our `start_hub.sh` launcher handles this by forcing Go to use the standard C library (cgo) DNS resolver:
```bash
export GODEBUG=netdns=cgo
```
Ensure this environment variable is present in the active startup environment if running manually outside of systemd.

---

## 5. Model Dropdown is empty or missing custom Gemini options

### Cause
Nginx is failing to route `/exa.language_server_pb.LanguageServerService/GetUserStatus` requests to the mock sidecar on port `8083`, or `ccpa_mock.py` crashed.

### Fix
1. Confirm `ccpa_mock.py` is running:
   ```bash
   ps aux | grep ccpa_mock.py
   ```
2. Verify Nginx can proxy to port `8083`:
   ```bash
   curl -I http://127.0.0.1:8083/
   ```
3. Restart Nginx and the web service to apply clean mappings:
   ```bash
   sudo systemctl restart nginx
   sudo systemctl restart antigravity-web.service
   ```

---

## 6. MCP Server Starts fail or report "failed to open port"

### Cause
Native MCP processes spawned by the Go `language_server` (e.g. from `~/.gemini/antigravity/mcp.json`) failed due to missing system package dependencies, incorrect execution paths, or stale subprocesses.

### Diagnostic Steps
1. **Check MCP Logs**: Look in `~/.gemini/antigravity/logs/` or check `language_server` stdout/stderr for any traceback from the MCP server.
2. **Clean Stale Subprocesses**:
   ```bash
   pkill -f mcp_deep_research || true
   ```
3. **Verify Dependencies**: If utilizing custom python-based MCP servers (such as Deep Research), verify that all packages are installed correctly:
   ```bash
   pip install --user --break-system-packages fastmcp
   ```
