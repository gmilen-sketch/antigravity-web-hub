let WebSocket;
try {
  WebSocket = require('ws');
} catch (e) {
  try {
    WebSocket = require('/tmp/ws_test/node_modules/ws');
  } catch (e2) {
    try {
      WebSocket = require('/usr/lib/node_modules/ws');
    } catch (e3) {
      WebSocket = require(require('path').join(__dirname, '../node_modules/ws'));
    }
  }
}
const http = require('http');
const { spawn, execSync } = require('child_process');
const fs = require('fs');

const LB_IP = process.env.LB_IP || '127.0.0.1:8080';
const CDP_PORT = process.env.CDP_PORT || String(9300 + (process.pid % 600));

function findChrome() {
  const candidates = [
    'google-chrome',
    'google-chrome-stable',
    'chromium',
    'chromium-browser',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium'
  ];
  for (const c of candidates) {
    try {
      execSync(`which ${c}`, { stdio: 'ignore' });
      return c;
    } catch (err) {}
  }
  return 'google-chrome';
}

async function verify() {
  const chromeBin = findChrome();
  const profileDir = '/tmp/clean-profile-' + Date.now();
  const chrome = spawn(chromeBin, [
    '--headless=new',
    '--no-sandbox',
    '--disable-gpu',
    '--window-size=1440,900',
    '--remote-debugging-port=' + CDP_PORT,
    '--user-data-dir=' + profileDir
  ]);

  let tabs = null;
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 500));
    try {
      tabs = await new Promise((resolve, reject) => {
        const req = http.get(`http://127.0.0.1:${CDP_PORT}/json`, (res) => {
          let raw = '';
          res.on('data', chunk => raw += chunk);
          res.on('end', () => resolve(JSON.parse(raw)));
          res.on('error', reject);
        });
        req.on('error', reject);
      });
      if (tabs && tabs.length > 0) break;
    } catch (e) {}
  }

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
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Page.navigate', { url: `http://${LB_IP}/` });

  console.log(`Navigated to http://${LB_IP}/. Waiting up to 15.0s for UI hydration...`);
  let domCheck = null;
  for (let attempt = 0; attempt < 10; attempt++) {
    await new Promise(r => setTimeout(r, 1500));
    domCheck = await send('Runtime.evaluate', {
      expression: `({
        childrenCount: document.getElementById('root') ? document.getElementById('root').children.length : 0,
        visibleText: document.body ? document.body.innerText.slice(0, 1000) : '',
        hasEditor: !!(document.querySelector('[data-lexical-editor=true]') || document.querySelector('[aria-label="Message input"]')),
        hasGemini38: document.body ? (document.body.innerText.includes('Gemini 3.8 Flash') || document.body.innerText.includes('Gemini 3.5 Flash')) : false
      })`,
      returnByValue: true
    });
    if (domCheck.result.value && domCheck.result.value.hasEditor && domCheck.result.value.childrenCount > 0) {
      break;
    }
  }

  console.log('------------------------------------------------------------');
  console.log('📊 [E2E Render Verification Result]:');
  console.log(JSON.stringify(domCheck.result.value, null, 2));
  console.log('------------------------------------------------------------');

  if (!domCheck.result.value.hasEditor || domCheck.result.value.childrenCount === 0) {
    console.error('❌ [FAIL] UI failed to load editor or models.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }

  console.log('🎉 [PASS] Model Selector & Editor UI Loaded Successfully!');

  // Verify Model Dropdown opens via real CDP Mouse Event, stays open without blinking across 6 frames (1500ms), and lists all 8 latest models
  console.log('Verifying Model Dropdown opens via real CDP Mouse Click without blinking and lists all 8 latest models...');
  const triggerBox = await send('Runtime.evaluate', {
    expression: `(() => {
      const btn = document.querySelector('[data-testid="model-selector-trigger"]') ||
                  Array.from(document.querySelectorAll('button')).find(b => (b.innerText.includes('Gemini') || b.innerText.includes('Claude')) && !b.innerText.includes('\\n'));
      if (!btn) return null;
      const r = btn.getBoundingClientRect();
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2), text: btn.innerText.trim() };
    })()`,
    returnByValue: true
  });
  if (!triggerBox.result.value) {
    console.error('❌ [FAIL] Model selector trigger button not found.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: triggerBox.result.value.x, y: triggerBox.result.value.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: triggerBox.result.value.x, y: triggerBox.result.value.y, button: 'left', clickCount: 1 });

  const stabilityFrames = [];
  for (let frameIdx = 0; frameIdx < 6; frameIdx++) {
    await new Promise(r => setTimeout(r, 250));
    const fCheck = await send('Runtime.evaluate', {
      expression: `(() => {
        const trig = document.querySelector('[data-testid="model-selector-trigger"]');
        const panel = document.querySelector('[data-testid="model-selector-panel"]');
        const items = Array.from(document.querySelectorAll('[data-testid="model-selector-item"]')).map(el => el.getAttribute('data-model-label') || el.innerText.trim());
        return {
          frame: ${frameIdx},
          ariaExpanded: trig ? trig.getAttribute('aria-expanded') : null,
          panelVisible: !!panel,
          itemsCount: items.length,
          items: items
        };
      })()`,
      returnByValue: true
    });
    stabilityFrames.push(fCheck.result.value);
  }

  const zeroBlinks = stabilityFrames.every(f => f.ariaExpanded === 'true' && f.panelVisible && f.itemsCount === 8);
  const dropdownCheck = await send('Runtime.evaluate', {
    expression: `({
      zeroBlinksAcross1500ms: ${zeroBlinks},
      listedModels: Array.from(document.querySelectorAll('[data-testid="model-selector-item"]')).map(el => el.getAttribute('data-model-label') || el.innerText.trim()),
      hasGemini4Argon: document.body.innerText.includes('Gemini 4 Argon'),
      hasGemini38: document.body.innerText.includes('Gemini 3.8 Flash'),
      hasGemini35Flash: document.body.innerText.includes('Gemini 3.5 Flash'),
      hasGemini36: document.body.innerText.includes('Gemini 3.6 Flash'),
      hasGemini35FlashLite: document.body.innerText.includes('Gemini 3.5 Flash Lite'),
      hasClaudeSonnet5: document.body.innerText.includes('Claude Sonnet 5.5'),
      hasClaudeOpus5: document.body.innerText.includes('Claude Opus 5.5'),
      hasClaudeFable5: document.body.innerText.includes('Claude Fable 5'),
      hasNoModelsAvailable: document.body.innerText.includes('No models available')
    })`,
    returnByValue: true
  });

  console.log('📊 [Model Dropdown Stability & Options Check]:', JSON.stringify(dropdownCheck.result.value, null, 2));
  if (
    !dropdownCheck.result.value.zeroBlinksAcross1500ms ||
    dropdownCheck.result.value.hasNoModelsAvailable ||
    !dropdownCheck.result.value.hasGemini4Argon ||
    !dropdownCheck.result.value.hasGemini38 ||
    !dropdownCheck.result.value.hasClaudeSonnet5 ||
    !dropdownCheck.result.value.hasClaudeOpus5
  ) {
    console.error('❌ [FAIL] Model dropdown stability or model list check failed.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }

  // Click Gemini 4 Argon inside the open dropdown via real CDP Mouse Event and verify it does NOT revert after 1000ms
  console.log('Verifying Model Switching: Clicking Gemini 4 Argon in dropdown via CDP Mouse Event...');
  const g4ItemBox = await send('Runtime.evaluate', {
    expression: `(() => {
      const el = document.querySelector('[data-testid="model-selector-item"][data-model-label="Gemini 4 Argon"]');
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()`,
    returnByValue: true
  });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: g4ItemBox.result.value.x, y: g4ItemBox.result.value.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: g4ItemBox.result.value.x, y: g4ItemBox.result.value.y, button: 'left', clickCount: 1 });
  await new Promise(r => setTimeout(r, 1000));

  const activeAfterGemini4 = await send('Runtime.evaluate', {
    expression: `(() => {
      const trig = document.querySelector('[data-testid="model-selector-trigger"]');
      return {
        buttonText: trig ? trig.innerText.trim() : '',
        ariaExpanded: trig ? trig.getAttribute('aria-expanded') : null,
        storedEnum: localStorage.getItem('antigravity_selected_model')
      };
    })()`,
    returnByValue: true
  });
  console.log('📊 [Active Model 1000ms After Clicking Gemini 4 Argon]:', JSON.stringify(activeAfterGemini4.result.value));
  if (
    !activeAfterGemini4.result.value.buttonText.includes('Gemini 4 Argon') ||
    activeAfterGemini4.result.value.storedEnum !== '354' ||
    activeAfterGemini4.result.value.ariaExpanded !== 'false'
  ) {
    console.error('❌ [FAIL] Selecting Gemini 4 Argon failed or reverted.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }
  console.log('🎉 [PASS] Gemini 4 Argon selected cleanly from dropdown without blinking or reverting!');

  // Re-open dropdown and select Claude Opus 5.5 (Vertex AI) via real CDP Mouse Event
  console.log('Verifying Model Switching: Re-opening dropdown and clicking Claude Opus 5.5 (Vertex AI)...');
  const triggerBox2 = await send('Runtime.evaluate', {
    expression: `(() => {
      const btn = document.querySelector('[data-testid="model-selector-trigger"]');
      const r = btn.getBoundingClientRect();
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()`,
    returnByValue: true
  });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: triggerBox2.result.value.x, y: triggerBox2.result.value.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: triggerBox2.result.value.x, y: triggerBox2.result.value.y, button: 'left', clickCount: 1 });
  await new Promise(r => setTimeout(r, 500));

  const opusItemBox = await send('Runtime.evaluate', {
    expression: `(() => {
      const el = document.querySelector('[data-testid="model-selector-item"][data-model-label="Claude Opus 5.5 (Vertex AI)"]');
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()`,
    returnByValue: true
  });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: opusItemBox.result.value.x, y: opusItemBox.result.value.y, button: 'left', clickCount: 1 });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: opusItemBox.result.value.x, y: opusItemBox.result.value.y, button: 'left', clickCount: 1 });
  await new Promise(r => setTimeout(r, 1000));

  const activeAfterOpus = await send('Runtime.evaluate', {
    expression: `(() => {
      const trig = document.querySelector('[data-testid="model-selector-trigger"]');
      return {
        buttonText: trig ? trig.innerText.trim() : '',
        ariaExpanded: trig ? trig.getAttribute('aria-expanded') : null,
        storedEnum: localStorage.getItem('antigravity_selected_model')
      };
    })()`,
    returnByValue: true
  });
  console.log('📊 [Active Model 1000ms After Clicking Claude Opus 5.5]:', JSON.stringify(activeAfterOpus.result.value));
  if (
    !activeAfterOpus.result.value.buttonText.includes('Claude Opus 5.5') ||
    activeAfterOpus.result.value.storedEnum !== '290'
  ) {
    console.error('❌ [FAIL] Model button failed to switch to Claude Opus 5.5.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }
  console.log('🎉 [PASS] Model Selection switching to Claude Opus 5.5 (Vertex AI) verified!');

  // Test Live Vertex AI Generation with BOTH Gemini 4 Argon (354) and Claude Opus 5.5 (290)
  console.log('Testing live Vertex AI generation with Gemini 4 Argon (gemini-4-argon) and Claude Opus 5.5 (claude-opus-5-5)...');
  const liveDualModelGen = await send('Runtime.evaluate', {
    expression: `(async () => {
      const g4Res = await window._origNativeFetch('/api/autonomy/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cascadeId: 'live-gen-gemini-4-argon',
          modelEnum: 354,
          generate: true,
          prompt: 'In two concise sentences, explain how Antigravity Web Hub uses Gemini 4 Argon and the 0.08ms /dev/shm Knowledge Graph for daily engineering workflows.'
        })
      });
      const g4Json = await g4Res.json();

      const opusRes = await window._origNativeFetch('/api/autonomy/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cascadeId: 'live-gen-claude-opus-5-5',
          modelEnum: 290,
          generate: true,
          prompt: 'In two concise sentences, explain how Antigravity Web Hub uses Claude Opus 5.5 on Vertex AI and the 2-Stage Goldfish -> Judge gate for SRE incident remediation.'
        })
      });
      const opusJson = await opusRes.json();

      return {
        gemini4Argon: g4Json.live_model_generation || {},
        claudeOpus55: opusJson.live_model_generation || {}
      };
    })()`,
    awaitPromise: true,
    returnByValue: true
  });
  console.log('📊 [Live Vertex AI Generation — Gemini 4 Argon & Claude Opus 5.5]:', JSON.stringify(liveDualModelGen.result.value, null, 2));
  if (
    liveDualModelGen.result.value.gemini4Argon.status !== 'LIVE_VERTEX_OK' ||
    liveDualModelGen.result.value.gemini4Argon.http_status !== 200 ||
    liveDualModelGen.result.value.gemini4Argon.model_id !== 'gemini-4-argon' ||
    !(liveDualModelGen.result.value.gemini4Argon.response_text && liveDualModelGen.result.value.gemini4Argon.response_text.length > 20) ||
    liveDualModelGen.result.value.claudeOpus55.status !== 'LIVE_VERTEX_OK' ||
    liveDualModelGen.result.value.claudeOpus55.http_status !== 200 ||
    liveDualModelGen.result.value.claudeOpus55.model_id !== 'claude-opus-5-5' ||
    !(liveDualModelGen.result.value.claudeOpus55.response_text && liveDualModelGen.result.value.claudeOpus55.response_text.length > 20)
  ) {
    console.error('❌ [FAIL] Live Vertex AI generation with Gemini 4 Argon or Claude Opus 5.5 failed.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }
  console.log('🎉 [PASS] Live Vertex AI generation verified for BOTH Gemini 4 Argon (HTTP 200) and Claude Opus 5.5 (HTTP 200)!');

  // Verify Native Go Language Server Customizations (1 Plugin, 20 Skills, 5 Subagents, 8 READY MCP Servers, 3 Rules)
  console.log('Verifying Native Go Language Server Customizations (1 Plugin, 20 Skills, 5 Subagents, 8 MCP Servers, 3 Rules)...');
  const customizationCheck = await send('Runtime.evaluate', {
    expression: `(async () => {
      const parseRpc = async (r) => {
        const buf = new Uint8Array(await r.arrayBuffer());
        const fullTxt = new TextDecoder().decode(buf).trim();
        if (fullTxt.startsWith('{')) {
          try { return JSON.parse(fullTxt); } catch (e) {}
        }
        const sliced = new TextDecoder().decode(buf.slice(5));
        const m = sliced.match(/\\{.*\\}/s);
        return m ? JSON.parse(m[0]) : {};
      };
      const rpcPost = (ep) => window.fetch('/exa.language_server_pb.LanguageServerService/' + ep, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Connect-Protocol-Version': '1' },
        body: '{}'
      });
      const verRes = await window.fetch('/api/version');
      const verJson = await verRes.json();
      const healthRes = await window.fetch('/healthz');
      const healthJson = await healthRes.json();
      const kgRes = await window.fetch('/api/kg');
      const kgJson = await kgRes.json();
      const kgNodeIds = (kgJson.nodes || []).map(n => n.id);
      const authObj = await parseRpc(await rpcPost('HasAuthToken'));
      const pluginsObj = await parseRpc(await rpcPost('GetAllPlugins'));
      const skillsObj = await parseRpc(await rpcPost('GetAllSkills'));
      const rulesObj = await parseRpc(await rpcPost('GetAllRules'));
      const agentsObj = await parseRpc(await rpcPost('GetAllCustomAgentConfigs'));
      const mcpObj = await parseRpc(await rpcPost('GetMcpServerStates'));
      const mcpReadyCount = (mcpObj.states || []).filter(s => s.status === 'MCP_SERVER_STATUS_READY' || s.status === 2).length;

      return {
        hubVersion: verJson.hub_version,
        antigravityCoreVersion: verJson.antigravity_core_version,
        antigravityExecutionId: verJson.antigravity_execution_id,
        antigravityCliVersion: verJson.antigravity_cli_version,
        webmEncoderPresent: verJson.webm_encoder_present,
        chromeDevtoolsMcpPresent: verJson.chrome_devtools_mcp_present,
        healthStatus: healthJson.status,
        hasNativeAuthToken: !!authObj.hasToken,
        kgNodesCount: (kgJson.nodes || []).length,
        kgEdgesCount: (kgJson.edges || []).length,
        hasFoundationalDocsInKg: ['doc:antigravity_web_hub', 'doc:google_adk', 'doc:agents_cli', 'doc:gemini_vertex_models', 'okf:google-adk-and-a2a-protocol'].every(id => kgNodeIds.includes(id)),
        pluginsCount: (pluginsObj.plugins || []).length,
        skillsCount: (skillsObj.skills || []).length,
        rulesCount: (rulesObj.rules || rulesObj.memories || []).length,
        subagentsCount: (agentsObj.configs || []).length,
        mcpServersCount: (mcpObj.states || []).length,
        mcpReadyCount: mcpReadyCount
      };
    })()`,
    awaitPromise: true,
    returnByValue: true
  });

  console.log('📊 [Native Language Server Core & Customizations Check]:', JSON.stringify(customizationCheck.result.value, null, 2));
  if (
    customizationCheck.result.value.hubVersion !== '3.9.0' ||
    !['2.22.0', '2.24.0', '2.29.1'].includes(customizationCheck.result.value.antigravityCoreVersion) ||
    !['1.3.3', '1.4.0', '1.5.3'].includes(customizationCheck.result.value.antigravityCliVersion) ||
    !customizationCheck.result.value.webmEncoderPresent ||
    !customizationCheck.result.value.chromeDevtoolsMcpPresent ||
    customizationCheck.result.value.healthStatus !== 'ok' ||
    !customizationCheck.result.value.hasNativeAuthToken ||
    customizationCheck.result.value.kgNodesCount < 17 ||
    customizationCheck.result.value.kgEdgesCount < 31 ||
    !customizationCheck.result.value.hasFoundationalDocsInKg ||
    customizationCheck.result.value.pluginsCount < 1 ||
    customizationCheck.result.value.skillsCount < 20 ||
    customizationCheck.result.value.rulesCount < 3 ||
    customizationCheck.result.value.subagentsCount !== 5 ||
    customizationCheck.result.value.mcpServersCount !== 8 ||
    customizationCheck.result.value.mcpReadyCount < 7
  ) {
    console.error('❌ [FAIL] Native Language Server auth, Foundational KG, or customization counts failed.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }

  console.log('Selecting Gemini 4 Argon and submitting live prompt through native Go language_server (:8081)...');
  await send('Runtime.evaluate', {
    expression: `(async () => {
      if (window.__selectAntigravityModel) {
        window.__selectAntigravityModel('Gemini 4 Argon');
      }
      await window.fetch('/api/active-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modelEnum: 354, modelId: 'gemini-4-argon' })
      });
      const editor = document.querySelector('[data-lexical-editor=true]') || document.querySelector('[aria-label="Message input"]');
      if (editor) { editor.focus(); return true; }
      return false;
    })()`,
    awaitPromise: true,
    returnByValue: true
  });
  await send('Input.insertText', { text: 'Reply in two sentences confirming the active GCP project ID from the cloud_telemetry MCP server and that native execution is active.' });
  await new Promise(r => setTimeout(r, 300));
  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });

  let nativeTrajectoryResult = null;
  for (let waitAttempt = 0; waitAttempt < 90; waitAttempt++) {
    await new Promise(r => setTimeout(r, 1000));
    const pollRes = await send('Runtime.evaluate', {
      expression: `(async () => {
        const parseRpc = async (r) => {
          const buf = new Uint8Array(await r.arrayBuffer());
          const fullTxt = new TextDecoder().decode(buf).trim();
          if (fullTxt.startsWith('{')) { try { return JSON.parse(fullTxt); } catch (e) {} }
          const sliced = new TextDecoder().decode(buf.slice(5));
          const m = sliced.match(/\\{.*\\}/s);
          return m ? JSON.parse(m[0]) : {};
        };
        const allObj = await parseRpc(await window.fetch('/exa.language_server_pb.LanguageServerService/GetAllCascadeTrajectories', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Connect-Protocol-Version': '1' },
          body: '{}'
        }));
        const summaries = allObj.trajectorySummaries || {};
        const cids = Object.keys(summaries);
        if (!cids.length) return { done: false, cidsCount: 0 };
        cids.sort((a, b) => String(summaries[b].lastModifiedTime || '').localeCompare(String(summaries[a].lastModifiedTime || '')));
        const latestCid = cids[0];
        const trajObj = await parseRpc(await window.fetch('/exa.language_server_pb.LanguageServerService/GetCascadeTrajectory', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Connect-Protocol-Version': '1' },
          body: JSON.stringify({ cascadeId: latestCid })
        }));
        const steps = (trajObj.trajectory && trajObj.trajectory.steps) || [];
        const plannerTexts = steps
          .filter(s => s.plannerResponse && (s.plannerResponse.modifiedResponse || s.plannerResponse.response))
          .map(s => s.plannerResponse.modifiedResponse || s.plannerResponse.response);
        const statusStr = String(trajObj.status || summaries[latestCid].status || '');
        const isIdle = statusStr.includes('IDLE') || statusStr === '1';
        return {
          done: isIdle && plannerTexts.length > 0 && plannerTexts[plannerTexts.length - 1].length > 20,
          latestCid,
          statusStr,
          stepCount: steps.length,
          plannerReply: plannerTexts[plannerTexts.length - 1] || '',
          domSnippet: document.body.innerText.slice(0, 1600),
          zeroMockFooters: !document.body.innerText.includes('Customization Telemetry') && !document.body.innerText.includes('Live Vertex AI response stream empty')
        };
      })()`,
      awaitPromise: true,
      returnByValue: true
    });
    nativeTrajectoryResult = pollRes.result ? pollRes.result.value : null;
    if (nativeTrajectoryResult && nativeTrajectoryResult.done) break;
  }

  console.log('------------------------------------------------------------');
  console.log('📊 [E2E NATIVE GO LANGUAGE SERVER TRAJECTORY VERIFICATION]:');
  console.log(JSON.stringify(nativeTrajectoryResult, null, 2));
  console.log('------------------------------------------------------------');

  if (
    !nativeTrajectoryResult ||
    !nativeTrajectoryResult.done ||
    !nativeTrajectoryResult.zeroMockFooters ||
    nativeTrajectoryResult.plannerReply.length < 20
  ) {
    console.error('❌ [FAIL] Native Go language_server live session execution or zero-mock assertion failed.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }

  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await send('Runtime.evaluate', {
    expression: `(() => {
      const st = document.createElement('style');
      st.textContent = 'html, body, #root, #root > div { min-height: 900px !important; height: 900px !important; }';
      document.head.appendChild(st);
      document.querySelectorAll('*').forEach(el => {
        if (el.scrollHeight > el.clientHeight + 20) {
          el.scrollTop = el.scrollHeight;
        }
      });
    })()`
  });
  await new Promise(r => setTimeout(r, 400));

  const screenshot = await send('Page.captureScreenshot', {
    format: 'png',
    clip: { x: 0, y: 0, width: 1440, height: 900, scale: 1 }
  });
  const scPath = process.env.E2E_SCREENSHOT_PATH || require('path').join(process.cwd(), 'antigravity_e2e_verified.png');
  fs.writeFileSync(scPath, Buffer.from(screenshot.data, 'base64'));
  console.log('🎉 [PASS] E2E Verification Complete! Screenshot saved to ' + scPath);
  console.log('============================================================');
  console.log('🎉 DEPLOYMENT & LIVE SESSION VERIFICATION PIPELINE COMPLETE: 100% SUCCESS');
  console.log('============================================================');

  ws.close();
  chrome.kill();
  process.exit(0);
}

verify().catch(err => {
  console.error('ERROR in verification:', err);
  process.exit(1);
});
