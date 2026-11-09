(function() {
  window.__APP_CONFIG__ = {
    productName: 'antigravity',
    csrfToken: 'antigravity_secret_csrf_token_12345',
    appVersion: '2.29.1',
    hubVersion: '3.9.0',
    releaseChannel: 'stable',
    devMode: false,
    nativeExecution: true
  };

  // Descriptive manifest metadata for the installed plugin bundle (never used to mock RPCs)
  window.__AGW_PLUGIN_CATALOG__ = {
    pluginId: 'antigravity-enterprise-autonomy',
    version: '3.9.0',
    rules: ['AGENTS.md', 'GEMINI.md', 'no-bullshit.md'],
    mcpServers: [
      { serverName: 'knowledge_graph' },
      { serverName: 'autonomy_engine' },
      { serverName: 'diagram_renderer' },
      { serverName: 'browser_cdp' },
      { serverName: 'cloud_telemetry' },
      { serverName: 'workspace_docs' },
      { serverName: 'deep_research' },
      { serverName: 'google_workspace' }
    ],
    skills: [
      'antigravity-web-builder',
      'black-hat-analysis',
      'diagram-renderer',
      'finops-focus-auditor',
      'first-principles-brainstormer',
      'golden-ab-testing',
      'idea-evaluator',
      'issue-tracker-manager',
      'migration-center-architect',
      'open-deep-researcher',
      'p0-quality-first-engine',
      'p1-quality-first-engine',
      'parallel-task-orchestrator',
      'playwright-agent-browser',
      'self-grill',
      'six-hats-evaluator',
      'universal-solution-architect',
      'universal-task-sync',
      'workspace-docs-publisher',
      'workspace-slides-generator'
    ]
  };

  try {
    document.cookie = 'csrfToken=antigravity_secret_csrf_token_12345; Path=/; SameSite=Lax';
    localStorage.setItem('antigravityOnboarding', 'true');
    localStorage.setItem('antigravityUnifiedStateSync.onboarding', 'true');
    localStorage.setItem('antigravity.isLoggedIn', 'true');
    localStorage.setItem('hasAuthToken', 'true');
    localStorage.setItem('isAuthenticated', 'true');
    if (!localStorage.getItem('antigravity_argon_default_v390')) {
      localStorage.setItem('antigravity_selected_model', '354');
      localStorage.setItem('antigravity_argon_default_v390', 'true');
    } else if (!localStorage.getItem('antigravity_selected_model')) {
      localStorage.setItem('antigravity_selected_model', '354');
    }
  } catch (e) {}

  var defaultItems = {
    'antigravityOnboarding': 'true',
    'antigravityUnifiedStateSync.onboarding': 'true',
    'antigravity.isLoggedIn': 'true',
    'hasAuthToken': 'true',
    'isAuthenticated': 'true',
    'antigravity_selected_model': '354',
    'selectedWorkspaceUri': 'file:///mnt/data/projects',
    'lastOpenedWorkspace': 'file:///mnt/data/projects'
  };

  var listeners = new Set();

  var revMap = {
    354: 'Gemini 4 Argon',
    352: 'Gemini 3.8 Flash',
    350: 'Gemini 3.5 Flash',
    348: 'Gemini 3.6 Flash',
    330: 'Gemini 3.5 Flash Lite',
    290: 'Claude Opus 5.5 (Vertex AI)',
    333: 'Claude Sonnet 5.5 (Vertex AI)',
    340: 'Claude Fable 5 (Next-Gen)'
  };

  var slugMap = {
    354: 'gemini-4-argon',
    352: 'gemini-3.8-flash',
    350: 'gemini-3.5-flash',
    348: 'gemini-3.6-flash',
    330: 'gemini-3.5-flash-lite',
    290: 'claude-opus-5-5',
    333: 'claude-sonnet-5-5',
    340: 'claude-fable-5'
  };

  var modelMap = {
    'Gemini 4 Argon': { name: 'Gemini 4 Argon', enumVal: 354 },
    'Gemini 4 Aragon (GA Flagship)': { name: 'Gemini 4 Argon', enumVal: 354 },
    'Gemini 4': { name: 'Gemini 4 Argon', enumVal: 354 },
    'Argon': { name: 'Gemini 4 Argon', enumVal: 354 },
    'Aragon': { name: 'Gemini 4 Argon', enumVal: 354 },
    'Gemini 3.8 Flash': { name: 'Gemini 3.8 Flash', enumVal: 352 },
    'Gemini 3.5 Flash': { name: 'Gemini 3.5 Flash', enumVal: 350 },
    'Gemini 3.6 Flash': { name: 'Gemini 3.6 Flash', enumVal: 348 },
    'Gemini 3.5 Flash Lite': { name: 'Gemini 3.5 Flash Lite', enumVal: 330 },
    'Claude Opus 5.5 (Vertex AI)': { name: 'Claude Opus 5.5 (Vertex AI)', enumVal: 290 },
    'Claude Opus 5.5': { name: 'Claude Opus 5.5 (Vertex AI)', enumVal: 290 },
    'Claude Opus 5': { name: 'Claude Opus 5.5 (Vertex AI)', enumVal: 290 },
    'Claude Sonnet 5.5 (Vertex AI)': { name: 'Claude Sonnet 5.5 (Vertex AI)', enumVal: 333 },
    'Claude Sonnet 5.5': { name: 'Claude Sonnet 5.5 (Vertex AI)', enumVal: 333 },
    'Claude Sonnet 5': { name: 'Claude Sonnet 5.5 (Vertex AI)', enumVal: 333 },
    'Claude Fable 5 (Next-Gen)': { name: 'Claude Fable 5 (Next-Gen)', enumVal: 340 },
    'Claude Fable 5': { name: 'Claude Fable 5 (Next-Gen)', enumVal: 340 }
  };

  function normalizeModelEnum(val) {
    if (val === null || val === undefined || val === '') return null;
    if (typeof val === 'number' && revMap[val]) return val;
    if (typeof val === 'object') {
      var inner = (val.choice && val.choice.value) || val.model || val.value;
      if (inner !== undefined) return normalizeModelEnum(inner);
      return null;
    }
    var s = String(val).trim();
    var su = s.toUpperCase();
    if (su === 'MODEL_PLACEHOLDER_M417' || su === 'MODEL_PLACEHOLDER_M418' || su === 'MODEL_PLACEHOLDER_M419') return 354;
    if (su === 'MODEL_PLACEHOLDER_M318' || su === 'MODEL_PLACEHOLDER_M319' || su === 'MODEL_PLACEHOLDER_M320') return 352;
    if (su === 'MODEL_PLACEHOLDER_M71' || su === 'MODEL_PLACEHOLDER_M72' || su === 'MODEL_PLACEHOLDER_M73') return 348;
    if (su === 'MODEL_PLACEHOLDER_M20' || su === 'MODEL_PLACEHOLDER_M149' || su === 'MODEL_PLACEHOLDER_M187') return 350;
    if (su === 'MODEL_PLACEHOLDER_M50') return 330;
    if (su === 'MODEL_PLACEHOLDER_M400' || su === 'MODEL_PLACEHOLDER_M401' || su === 'MODEL_PLACEHOLDER_M402' || su === 'MODEL_PLACEHOLDER_M406') return 290;
    if (su.indexOf('_SAMPLER') !== -1 || su.indexOf('EXAMPLE_') !== -1 || su.indexOf('ARGON') !== -1 || su.indexOf('ARAGON') !== -1) return 354;
    if (su.indexOf('_THINKING_LOW') !== -1 || su.indexOf('_THINKING_HIGH') !== -1) return 352;
    if (su.indexOf('CLAUDE') !== -1 && su.indexOf('OPUS') !== -1) return 290;
    if (su.indexOf('CLAUDE') !== -1 && su.indexOf('SONNET') !== -1) return 333;
    if (su.indexOf('CLAUDE') !== -1 && su.indexOf('HAIKU') !== -1) return 340;
    if (su.indexOf('_LITE') !== -1) return 330;
    if (su.slice(-3) === 'JET') return 350;
    if (su.slice(-6) === 'RUNNER') return 348;
    var asInt = parseInt(s, 10);
    if (!isNaN(asInt) && revMap[asInt]) return asInt;
    for (var key in modelMap) {
      if (s === key || s.indexOf(key) !== -1) {
        return modelMap[key].enumVal;
      }
    }
    return null;
  }

  function syncActiveModelToGateway(enumVal) {
    try {
      var fn = window._origNativeFetch || window.fetch;
      fn('/api/active-model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modelEnum: enumVal, modelId: slugMap[enumVal] || 'gemini-4-argon' })
      }).catch(function() {});
    } catch (e) {}
  }

  var initialSavedModel = normalizeModelEnum(localStorage.getItem('antigravity_selected_model')) || 354;
  var currentSelectedModel = initialSavedModel;
  try {
    localStorage.setItem('antigravity_selected_model', String(currentSelectedModel));
  } catch (e) {}

  function isModelMenuOpen() {
    try {
      var trig = document.querySelector('[data-testid="model-selector-trigger"]');
      if (trig && trig.getAttribute('aria-expanded') === 'true') return true;
      if (document.querySelector('[data-testid="model-selector-panel"], [role="menu"][data-open]')) return true;
    } catch (e) {}
    return false;
  }

  function updateModelButtonText(modelName, forceUpdate) {
    if (!modelName) return;
    if (!forceUpdate && isModelMenuOpen()) return;
    var mainBtn = document.querySelector('[data-testid="model-selector-trigger"]');
    if (!mainBtn) {
      var btns = Array.from(document.querySelectorAll('button'));
      mainBtn = btns.find(function(b) {
        if (b.closest('[role="menu"], [role="listbox"], [data-radix-popper-content-wrapper], [data-base-ui-portal]')) return false;
        var t = b.innerText || '';
        return (t.indexOf('Gemini') !== -1 || t.indexOf('Claude') !== -1) && t.indexOf('\n') === -1;
      });
    }
    if (mainBtn) {
      var walker = document.createTreeWalker(mainBtn, NodeFilter.SHOW_TEXT, null, false);
      var node;
      var updated = false;
      while ((node = walker.nextNode())) {
        if (node.nodeValue && (node.nodeValue.indexOf('Gemini') !== -1 || node.nodeValue.indexOf('Claude') !== -1)) {
          if (node.nodeValue !== modelName) {
            node.nodeValue = modelName;
          }
          updated = true;
        }
      }
      if (!updated && mainBtn.innerText.trim() !== modelName) {
        var spanEl = mainBtn.querySelector('span');
        if (spanEl) {
          spanEl.textContent = modelName;
        } else {
          mainBtn.innerText = modelName;
        }
      }
      var expectedAria = 'Select model, current: ' + modelName;
      if (mainBtn.getAttribute('aria-label') !== expectedAria) {
        mainBtn.setAttribute('aria-label', expectedAria);
      }
    }
  }

  window.__selectAntigravityModel = function(keyOrName) {
    var enumVal = normalizeModelEnum(keyOrName);
    if (!enumVal) {
      for (var key in modelMap) {
        if (String(keyOrName).indexOf(key) !== -1 || key.indexOf(String(keyOrName)) !== -1) {
          enumVal = modelMap[key].enumVal;
          break;
        }
      }
    }
    if (enumVal && revMap[enumVal]) {
      var matchedName = revMap[enumVal];
      currentSelectedModel = enumVal;
      try { localStorage.setItem('antigravity_selected_model', String(enumVal)); } catch (err) {}
      syncActiveModelToGateway(enumVal);
      updateModelButtonText(matchedName, true);
      setTimeout(function() { updateModelButtonText(matchedName, true); }, 60);
      setTimeout(function() { updateModelButtonText(matchedName, true); }, 180);
      return { name: matchedName, enumVal: enumVal };
    }
    return null;
  };

  document.addEventListener('click', function(e) {
    var target = e.target;
    if (!target || !target.closest) return;
    if (target.closest('[data-testid="model-selector-trigger"]')) return;
    var menuItem = target.closest('[data-testid="model-selector-item"], [data-model-label]');
    if (!menuItem) {
      var inMenu = target.closest('[data-testid="model-selector-panel"], [role="menu"]');
      if (inMenu) {
        menuItem = target.closest('[role="menuitem"], [role="option"]');
      }
    }
    if (!menuItem) return;
    var rawLabel = menuItem.getAttribute('data-model-label') || ((menuItem.innerText || menuItem.textContent || '').split('\n')[0] || '').trim();
    if (!rawLabel || rawLabel === 'View Usage' || rawLabel === 'Model') return;
    window.__selectAntigravityModel(rawLabel);
  }, true);

  setInterval(function() {
    if (isModelMenuOpen()) return;
    var rawSaved = localStorage.getItem('antigravity_selected_model');
    var normSaved = normalizeModelEnum(rawSaved) || currentSelectedModel || 354;
    if (String(normSaved) !== rawSaved) {
      try { localStorage.setItem('antigravity_selected_model', String(normSaved)); } catch (e) {}
    }
    currentSelectedModel = normSaved;
    updateModelButtonText(revMap[normSaved] || 'Gemini 4 Argon', false);
  }, 300);

  window.nativeStorage = {
    getItems: async function(keys) {
      var res = {};
      var targetKeys = (!keys || !Array.isArray(keys) || keys.length === 0) ? Object.keys(defaultItems) : keys;
      for (var i = 0; i < targetKeys.length; i++) {
        var k = targetKeys[i];
        var val = null;
        try { val = localStorage.getItem(k); } catch (e) {}
        res[k] = val !== null ? val : (defaultItems[k] !== undefined ? defaultItems[k] : null);
      }
      return Object.assign({}, res, { items: res });
    },
    updateItems: async function(items) {
      if (items && typeof items === 'object') {
        for (var k in items) {
          try { localStorage.setItem(k, items[k]); } catch (e) {}
        }
        listeners.forEach(function(cb) { try { cb(items); } catch (e) {} });
      }
      return {};
    },
    getItem: async function(key) {
      try {
        var v = localStorage.getItem(key);
        if (v !== null) return v;
      } catch (e) {}
      return defaultItems[key] !== undefined ? defaultItems[key] : null;
    },
    setItem: async function(key, val) {
      try { localStorage.setItem(key, val); } catch (e) {}
      var patch = {};
      patch[key] = val;
      listeners.forEach(function(cb) { try { cb(patch); } catch (e) {} });
      return {};
    },
    removeItem: async function(key) {
      try { localStorage.removeItem(key); } catch (e) {}
      return {};
    },
    onChanged: function(cb) {
      if (typeof cb === 'function') listeners.add(cb);
      return function() { listeners.delete(cb); };
    }
  };

  window.electronNative = {
    getZoomLevel: async function() { return 0; },
    setZoomLevel: async function() { return 0; },
    openExternal: async function(url) { window.open(url, '_blank', 'noopener,noreferrer'); },
    getPlatform: function() { return 'linux'; }
  };

  function encodeGrpcFrame(obj) {
    var payload = new TextEncoder().encode(JSON.stringify(obj));
    var trailer = new TextEncoder().encode('grpc-status: 0\r\n');
    var out = new Uint8Array(5 + payload.length + 5 + trailer.length);
    out[0] = 0x00;
    new DataView(out.buffer).setUint32(1, payload.length, false);
    out.set(payload, 5);
    var tOff = 5 + payload.length;
    out[tOff] = 0x80;
    new DataView(out.buffer).setUint32(tOff + 1, trailer.length, false);
    out.set(trailer, tOff + 5);
    return new Response(out, {
      status: 200,
      headers: { 'Content-Type': 'application/grpc-web+json' }
    });
  }

  function encodeGrpcKeepOpenStream(initialObj) {
    var payload = new TextEncoder().encode(JSON.stringify(initialObj));
    var frame = new Uint8Array(5 + payload.length);
    frame[0] = 0x00;
    new DataView(frame.buffer).setUint32(1, payload.length, false);
    frame.set(payload, 5);
    var stream = new ReadableStream({
      start: function(controller) {
        controller.enqueue(frame);
      }
    });
    return new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'application/grpc-web+json' }
    });
  }

  if (!window._origNativeFetch) {
    window._origNativeFetch = window.fetch.bind(window);
    syncActiveModelToGateway(currentSelectedModel);

    // Pass 100% of cascade, streaming, tool, trajectory, MCP, plugin, skill, and rule RPCs straight to native :8081.
    // Only provide Electron-IPC hydration polyfills for desktop-only shell state when standalone :8081 omits them.
    window.fetch = async function() {
      var args = Array.prototype.slice.call(arguments);
      var url = typeof args[0] === 'string' ? args[0] : ((args[0] && args[0].url) || '');

      // Desktop Electron shell state stream required by root React mount ($5a.initialized) in standalone browser mode
      if (url.indexOf('JetboxSubscribeToState') !== -1 || url.indexOf('jetboxSubscribeToState') !== -1) {
        return encodeGrpcKeepOpenStream({
          appState: {
            agentOnboardingCompleted: 2,
            postOnboarding: { completedSteps: [1, 2, 3, 4] }
          },
          userConfig: {}
        });
      }

      if (url.indexOf('GetLocalUserInfo') !== -1 || url.indexOf('getLocalUserInfo') !== -1) {
        var origRes = await window._origNativeFetch.apply(this, args);
        if (origRes.ok) return origRes;
        return encodeGrpcFrame({
          username: 'enterprise_cloud_admin',
          homeDirUri: 'file:///mnt/data/projects'
        });
      }

      return window._origNativeFetch.apply(this, args);
    };
  }
})();
