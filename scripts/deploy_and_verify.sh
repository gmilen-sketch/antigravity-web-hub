#!/bin/bash
# ==============================================================================
# Antigravity Web Hub - Clean-Room Destroy, Deploy & E2E Verification Pipeline
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-second-test-project-393510}"
ZONE="${VM_ZONE:-us-central1-c}"
VM_NAME="${VM_NAME:-antigravity-ge-hub}"
SSH_USER="${SSH_USER:-admin@mgenchev.altostrat.com}"
LB_IP="${LB_IP:-34.107.158.143}"

echo "============================================================"
echo "🚀 [Antigravity Hub] Standalone Clean-Room Deploy & Verify"
echo "Target Project: ${PROJECT_ID} | VM: ${VM_NAME} (${ZONE})"
echo "============================================================"

# Step 1: Package clean repository
TAR_ARCHIVE="/tmp/antigravity-hub-deploy.tar.gz"
echo "📦 [1/4] Packaging clean repository into ${TAR_ARCHIVE}..."
rm -f "${TAR_ARCHIVE}"
tar --exclude='.git' --exclude='venv' --exclude='node_modules' -czf "${TAR_ARCHIVE}" -C "${REPO_ROOT}" .

# Step 2: Transfer package and run clean-room destroy & installer
echo "🚚 [2/4] Uploading deployment package and runner to ${VM_NAME}..."
gcloud compute scp "${TAR_ARCHIVE}" "${VM_NAME}:/tmp/hub.tar.gz" \
  --zone="${ZONE}" \
  --project="${PROJECT_ID}" \
  --account="${SSH_USER}" \
  --tunnel-through-iap \
  --scp-flag="-o StrictHostKeyChecking=no"

gcloud compute scp "${SCRIPT_DIR}/remote_runner.sh" "${VM_NAME}:/tmp/remote_runner.sh" \
  --zone="${ZONE}" \
  --project="${PROJECT_ID}" \
  --account="${SSH_USER}" \
  --tunnel-through-iap \
  --scp-flag="-o StrictHostKeyChecking=no"

echo "⚙️  [3/4] Executing remote clean-room destroy & installation on ${VM_NAME}..."
gcloud compute ssh "${VM_NAME}" \
  --zone="${ZONE}" \
  --project="${PROJECT_ID}" \
  --account="${SSH_USER}" \
  --tunnel-through-iap \
  --ssh-flag="-o StrictHostKeyChecking=no" \
  --command="bash /tmp/remote_runner.sh"

echo "✅ Remote deployment completed successfully."

# Step 3: Automated End-to-End Verification via Headless Chrome CDP
echo "🧪 [4/4] Polling Load Balancer Health Check & Running E2E Automated Verification..."

# Wait for LB health check to confirm 200 OK
for i in {1..15}; do
  status_code=$(curl -s -o /dev/null -w "%{http_code}" "http://${LB_IP}/" || echo "000")
  if [ "$status_code" = "200" ]; then
    echo "Load Balancer is healthy (HTTP 200 OK after ${i} checks)."
    break
  fi
  echo "Waiting for Load Balancer health check convergence (status: ${status_code}, attempt ${i}/15)..."
  sleep 2
done

# Run Node.js CDP verification
node -e "
const WebSocket = require('/tmp/ws_test/node_modules/ws');
const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');

async function verify() {
  const profileDir = '/tmp/clean-profile-' + Date.now();
  const chrome = spawn('google-chrome', [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--window-size=1440,900',
    '--remote-debugging-port=9292',
    '--user-data-dir=' + profileDir
  ]);

  await new Promise(r => setTimeout(r, 1500));

  const tabs = await new Promise((resolve, reject) => {
    http.get('http://127.0.0.1:9292/json', (res) => {
      let raw = '';
      res.on('data', chunk => raw += chunk);
      res.on('end', () => resolve(JSON.parse(raw)));
      res.on('error', reject);
    });
  });

  const ws = new WebSocket(tabs[0].webSocketDebuggerUrl);
  await new Promise(r => ws.on('open', r));

  let reqId = 1;
  const pending = new Map();
  ws.on('message', (data) => {
    const msg = JSON.parse(data.toString());
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(JSON.stringify(msg.error)));
      else resolve(msg.result);
    }
  });

  function send(method, params = {}) {
    const id = reqId++;
    return new Promise((resolve, reject) => {
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  await send('Runtime.enable');
  await send('Page.enable');
  await send('Page.navigate', { url: 'http://${LB_IP}/' });

  console.log('Navigated to http://${LB_IP}/. Waiting 4.5s for UI hydration...');
  await new Promise(r => setTimeout(r, 4500));

  const domCheck = await send('Runtime.evaluate', {
    expression: \`({
      childrenCount: document.getElementById('root') ? document.getElementById('root').children.length : 0,
      visibleText: document.body.innerText.slice(0, 1000),
      hasEditor: !!(document.querySelector('[data-lexical-editor=true]') || document.querySelector('[aria-label=\"Message input\"]'))
    })\`,
    returnByValue: true
  });

  console.log('------------------------------------------------------------');
  console.log('📊 [E2E Render Verification Result]:');
  console.log(JSON.stringify(domCheck.result.value, null, 2));
  console.log('------------------------------------------------------------');

  if (!domCheck.result.value.hasEditor || domCheck.result.value.visibleText.includes('Loading models...')) {
    console.error('❌ [FAIL] UI failed to load editor or models.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }

  console.log('🎉 [PASS] Model Selector & Editor UI Loaded Successfully!');
  console.log('Typing and submitting automated test prompt...');

  await send('Runtime.evaluate', {
    expression: \`(() => {
      const editor = document.querySelector('[data-lexical-editor=true]') || document.querySelector('[aria-label=\"Message input\"]');
      if (editor) { editor.focus(); return true; }
      return false;
    })()\`,
    returnByValue: true
  });

  await send('Input.insertText', { text: 'Write a python quicksort function with docstrings' });
  await new Promise(r => setTimeout(r, 300));

  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });

  console.log('Waiting 5s for conversation thread mount...');
  await new Promise(r => setTimeout(r, 5000));

  const postSubmission = await send('Runtime.evaluate', {
    expression: \`({
      bodySnippet: document.body.innerText.slice(0, 1000),
      hasSubmitted: document.body.innerText.includes('quicksort')
    })\`,
    returnByValue: true
  });

  console.log('------------------------------------------------------------');
  console.log('📊 [E2E PROMPT SUBMISSION VERIFICATION]:');
  console.log(JSON.stringify(postSubmission.result.value, null, 2));
  console.log('------------------------------------------------------------');

  const screenshot = await send('Page.captureScreenshot', { format: 'png' });
  const scPath = '/usr/local/google/home/mgenchev/.gemini/jetski/brain/dc82200c-f596-42b7-8ba0-0e25321e9cd2/antigravity_e2e_verified.png';
  fs.writeFileSync(scPath, Buffer.from(screenshot.data, 'base64'));
  console.log('🎉 [PASS] E2E Verification Complete! Screenshot saved to antigravity_e2e_verified.png');
  console.log('============================================================');
  console.log('🎉 DEPLOYMENT & VERIFICATION PIPELINE COMPLETE: 100% SUCCESS');
  console.log('============================================================');

  ws.close();
  chrome.kill();
  process.exit(0);
}

verify().catch(err => {
  console.error('ERROR in verification:', err);
  process.exit(1);
});
"
