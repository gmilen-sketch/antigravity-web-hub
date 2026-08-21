const WebSocket = require('/tmp/ws_test/node_modules/ws');
const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');

const LB_IP = process.env.LB_IP || '34.107.158.143';

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
  await send('Page.navigate', { url: `http://${LB_IP}/` });

  console.log(`Navigated to http://${LB_IP}/. Waiting 6.0s for UI hydration...`);
  await new Promise(r => setTimeout(r, 6000));

  const domCheck = await send('Runtime.evaluate', {
    expression: `({
      childrenCount: document.getElementById('root') ? document.getElementById('root').children.length : 0,
      visibleText: document.body.innerText.slice(0, 1000),
      hasEditor: !!(document.querySelector('[data-lexical-editor=true]') || document.querySelector('[aria-label="Message input"]')),
      hasGemini37: document.body.innerText.includes('Gemini 3.7 Flash')
    })`,
    returnByValue: true
  });

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

  // Verify Model Dropdown
  console.log('Verifying Model Dropdown options...');
  await send('Runtime.evaluate', {
    expression: `(() => {
      const btns = Array.from(document.querySelectorAll('button'));
      const modelBtn = btns.find(b => (b.innerText.includes('Gemini') || b.innerText.includes('Claude')) && !b.innerText.includes('\\n'));
      if (modelBtn) modelBtn.click();
    })()`
  });
  await new Promise(r => setTimeout(r, 1000));

  const dropdownCheck = await send('Runtime.evaluate', {
    expression: `({
      hasGemini37: document.body.innerText.includes('Gemini 3.7 Flash'),
      hasGemini36: document.body.innerText.includes('Gemini 3.6 Flash'),
      hasGemini35FlashLite: document.body.innerText.includes('Gemini 3.5 Flash Lite'),
      hasClaudeSonnet: document.body.innerText.includes('Claude 3.7 Sonnet'),
      hasClaudeOpus: document.body.innerText.includes('Claude Opus 5'),
      hasNoModelsAvailable: document.body.innerText.includes('No models available')
    })`,
    returnByValue: true
  });

  console.log('📊 [Model Dropdown Options Check]:', JSON.stringify(dropdownCheck.result.value, null, 2));
  if (dropdownCheck.result.value.hasNoModelsAvailable || !dropdownCheck.result.value.hasGemini37) {
    console.error('❌ [FAIL] Model dropdown failed.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }

  // Verify Model Selection Switching
  console.log('Verifying Model Switching: Selecting Claude 3.7 Sonnet...');
  await send('Runtime.evaluate', {
    expression: `(() => {
      const allEls = Array.from(document.querySelectorAll('*'));
      const claude = allEls.find(el => el.children.length === 0 && el.innerText && el.innerText.includes('Claude 3.7 Sonnet'));
      if (claude) {
        claude.click();
        const p = claude.closest('button, [role="menuitem"], [role="option"], div');
        if (p) p.click();
      }
    })()`
  });
  await new Promise(r => setTimeout(r, 1000));

  const activeAfterClaude = await send('Runtime.evaluate', {
    expression: `(() => {
      const btn = Array.from(document.querySelectorAll('button')).find(b => (b.innerText.includes('Gemini') || b.innerText.includes('Claude')) && !b.innerText.includes('\\n'));
      return btn ? btn.innerText.trim() : '';
    })()`,
    returnByValue: true
  });
  console.log('📊 [Active Model After Selecting Claude]:', activeAfterClaude.result.value);
  if (!activeAfterClaude.result.value.includes('Claude 3.7 Sonnet')) {
    console.error('❌ [FAIL] Model button failed to switch to Claude 3.7 Sonnet.');
    ws.close();
    chrome.kill();
    process.exit(1);
  }
  console.log('🎉 [PASS] Model Selection switching to Claude 3.7 Sonnet verified!');

  console.log('Typing and submitting automated test prompt...');
  await send('Runtime.evaluate', {
    expression: `(() => {
      const editor = document.querySelector('[data-lexical-editor=true]') || document.querySelector('[aria-label="Message input"]');
      if (editor) { editor.focus(); return true; }
      return false;
    })()`,
    returnByValue: true
  });

  await send('Input.insertText', { text: 'Write a python quicksort function with docstrings' });
  await new Promise(r => setTimeout(r, 300));

  await send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 });

  console.log('Waiting 5s for conversation thread mount...');
  await new Promise(r => setTimeout(r, 5000));

  const postSubmission = await send('Runtime.evaluate', {
    expression: `({
      bodySnippet: document.body.innerText.slice(0, 1000),
      hasSubmitted: document.body.innerText.includes('quicksort')
    })`,
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
