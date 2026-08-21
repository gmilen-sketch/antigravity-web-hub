(function() {
  window.__APP_CONFIG__ = {
    productName: 'antigravity',
    csrfToken: 'antigravity_secret_csrf_token_12345',
    appVersion: '3.1.0',
    devMode: false
  };

  try {
    document.cookie = 'csrfToken=antigravity_secret_csrf_token_12345; Path=/; SameSite=Lax';
    localStorage.setItem('antigravityOnboarding', 'true');
    localStorage.setItem('antigravityUnifiedStateSync.onboarding', 'true');
    localStorage.setItem('antigravity.isLoggedIn', 'true');
    localStorage.setItem('hasAuthToken', 'true');
    localStorage.setItem('isAuthenticated', 'true');
  } catch (e) {}

  var defaultItems = {
    'antigravityOnboarding': 'true',
    'antigravityUnifiedStateSync.onboarding': 'true',
    'antigravity.isLoggedIn': 'true',
    'hasAuthToken': 'true',
    'isAuthenticated': 'true'
  };

  var listeners = new Set();
  var currentSelectedModel = parseInt(localStorage.getItem('antigravity_selected_model') || '352', 10);

  var revMap = {
    352: 'Gemini 3.7 Flash',
    350: 'Gemini 3.6 Flash',
    330: 'Gemini 3.5 Flash Lite',
    333: 'Claude 3.7 Sonnet (Vertex AI)',
    290: 'Claude Opus 5 (Vertex AI)'
  };

  var modelMap = {
    'Claude 3.7 Sonnet': { name: 'Claude 3.7 Sonnet (Vertex AI)', enumVal: 333 },
    'Claude Opus 5': { name: 'Claude Opus 5 (Vertex AI)', enumVal: 290 },
    'Gemini 3.6 Flash': { name: 'Gemini 3.6 Flash', enumVal: 350 },
    'Gemini 3.5 Flash Lite': { name: 'Gemini 3.5 Flash Lite', enumVal: 330 },
    'Gemini 3.7 Flash': { name: 'Gemini 3.7 Flash', enumVal: 352 }
  };

  function updateModelButtonText(modelName) {
    var btns = Array.from(document.querySelectorAll('button'));
    var mainBtn = btns.find(function(b) {
      var t = b.innerText || '';
      return (t.indexOf('Gemini') !== -1 || t.indexOf('Claude') !== -1) && t.indexOf('\n') === -1;
    });
    if (mainBtn) {
      var span = mainBtn.querySelector('span');
      if (span && span.innerText !== modelName) {
        span.innerText = modelName;
      } else if (!span && mainBtn.innerText !== modelName) {
        mainBtn.innerText = modelName;
      }
      mainBtn.setAttribute('aria-label', 'Select model, current: ' + modelName);
    }
  }

  document.addEventListener('click', function(e) {
    var target = e.target;
    while (target && target !== document.body) {
      if (target.tagName === 'BUTTON' || target.getAttribute('role') === 'button') {
        var text = target.innerText || '';
        var aria = target.getAttribute('aria-label') || '';
        if (aria.indexOf('Select model, current') === -1) {
          for (var key in modelMap) {
            if (text.indexOf(key) !== -1) {
              var matched = modelMap[key];
              currentSelectedModel = matched.enumVal;
              try { localStorage.setItem('antigravity_selected_model', String(matched.enumVal)); } catch (err) {}
              console.log('[Bootstrap] User selected model:', matched.name, matched.enumVal);
              updateModelButtonText(matched.name);
              setTimeout(function() { updateModelButtonText(matched.name); }, 50);
              setTimeout(function() { updateModelButtonText(matched.name); }, 150);
              setTimeout(function() { updateModelButtonText(matched.name); }, 400);
              return;
            }
          }
        }
      }
      target = target.parentElement;
    }
  }, true);

  setInterval(function() {
    var saved = parseInt(localStorage.getItem('antigravity_selected_model') || '352', 10);
    var modelName = revMap[saved] || 'Gemini 3.7 Flash';
    updateModelButtonText(modelName);
  }, 250);

  window.nativeStorage = {
    getItems: async function(keys) {
      var r = Object.assign({}, defaultItems);
      try {
        for (var i = 0; i < localStorage.length; i++) {
          var k = localStorage.key(i);
          if (k) r[k] = localStorage.getItem(k);
        }
      } catch (e) {}
      if (keys && Array.isArray(keys) && keys.length > 0) {
        var filtered = {};
        for (var j = 0; j < keys.length; j++) {
          filtered[keys[j]] = r[keys[j]] || 'true';
        }
        return filtered;
      }
      return r;
    },
    updateItems: async function(updates) {
      if (!updates) return;
      for (var k in updates) {
        var v = updates[k];
        if (v === null || v === undefined) {
          try { localStorage.removeItem(k); } catch (e) {}
          delete defaultItems[k];
        } else {
          var val = typeof v === 'string' ? v : JSON.stringify(v);
          try { localStorage.setItem(k, val); } catch (e) {}
          defaultItems[k] = val;
        }
      }
      listeners.forEach(function(cb) { try { cb(updates); } catch (e) {} });
    },
    getItem: async function(key) {
      try { return localStorage.getItem(key) || defaultItems[key] || 'true'; } catch (e) { return defaultItems[key] || 'true'; }
    },
    setItem: async function(key, value) {
      var up = {};
      up[key] = value;
      return this.updateItems(up);
    },
    removeItem: async function(key) {
      var up = {};
      up[key] = null;
      return this.updateItems(up);
    },
    onChanged: function(callback) {
      listeners.add(callback);
      return function() { listeners.delete(callback); };
    }
  };

  window.electronNative = {
    getZoomLevel: function() { return 1; },
    setZoomLevel: function() {},
    openExternal: function(url) { window.open(url, '_blank'); },
    getSystemPreferences: async function() { return {}; },
    openSystemPreferences: async function() {},
    showNotification: function() {},
    getPlatform: function() { return 'linux'; },
    invoke: async function() { return null; },
    send: function() {},
    on: function() { return function() {}; },
    removeAllListeners: function() {}
  };

  function makeGrpcWeb(doc) {
    var enc = new TextEncoder().encode(JSON.stringify(doc));
    var crlf = String.fromCharCode(13, 10);
    var trailer = new TextEncoder().encode('grpc-status: 0' + crlf);
    var dataHeader = new Uint8Array([0x00, (enc.length >> 24) & 0xff, (enc.length >> 16) & 0xff, (enc.length >> 8) & 0xff, enc.length & 0xff]);
    var trailerHeader = new Uint8Array([0x80, (trailer.length >> 24) & 0xff, (trailer.length >> 16) & 0xff, (trailer.length >> 8) & 0xff, trailer.length & 0xff]);
    var combined = new Uint8Array(5 + enc.length + 5 + trailer.length);
    combined.set(dataHeader, 0);
    combined.set(enc, 5);
    combined.set(trailerHeader, 5 + enc.length);
    combined.set(trailer, 5 + enc.length + 5);

    return new Response(combined, {
      status: 200,
      headers: {
        'Content-Type': 'application/grpc-web+json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Expose-Headers': 'Content-Length,Content-Range,grpc-status,grpc-message,grpc-status-details-bin,connect-protocol-version,grpc-encoding,grpc-accept-encoding,Grpc-Status,Grpc-Message,Grpc-Status-Details-Bin'
      }
    });
  }

  function makeStreamWithInitialMessage(doc) {
    var enc = new TextEncoder().encode(JSON.stringify(doc));
    var dataHeader = new Uint8Array([0x00, (enc.length >> 24) & 0xff, (enc.length >> 16) & 0xff, (enc.length >> 8) & 0xff, enc.length & 0xff]);
    var chunk = new Uint8Array(5 + enc.length);
    chunk.set(dataHeader, 0);
    chunk.set(enc, 5);

    return new Response(new ReadableStream({
      start: function(controller) {
        controller.enqueue(chunk);
      }
    }), {
      status: 200,
      headers: {
        'Content-Type': 'application/grpc-web+json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Expose-Headers': 'Content-Length,Content-Range,grpc-status,grpc-message,grpc-status-details-bin,connect-protocol-version,grpc-encoding,grpc-accept-encoding,Grpc-Status,Grpc-Message,Grpc-Status-Details-Bin'
      }
    });
  }

  var defaultCascadeModelConfigData = {
    clientModelConfigs: [
      {
        label: 'Gemini 3.7 Flash',
        modelOrAlias: { choice: { case: 'model', value: 352 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Recommended',
        tagDescription: 'High-speed reasoning and code generation',
        supportsThoughtCirculation: true
      },
      {
        label: 'Gemini 3.6 Flash',
        modelOrAlias: { choice: { case: 'model', value: 350 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'General Production',
        tagDescription: 'Multimodal and coding agent tasks',
        supportsThoughtCirculation: true
      },
      {
        label: 'Gemini 3.5 Flash Lite',
        modelOrAlias: { choice: { case: 'model', value: 330 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'High-Throughput',
        tagDescription: 'Low-latency extraction and routing',
        supportsThoughtCirculation: true
      },
      {
        label: 'Claude 3.7 Sonnet (Vertex AI)',
        modelOrAlias: { choice: { case: 'model', value: 333 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Complex Reasoning',
        tagDescription: 'Extended context and deep synthesis',
        supportsThoughtCirculation: true
      },
      {
        label: 'Claude Opus 5 (Vertex AI)',
        modelOrAlias: { choice: { case: 'model', value: 290 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Deep Reasoning',
        tagDescription: 'Large-scale architectural analysis',
        supportsThoughtCirculation: true
      }
    ],
    clientModelSorts: [
      {
        name: 'Recommended',
        groups: [
          {
            groupName: 'Recommended',
            modelLabels: [
              'Gemini 3.7 Flash',
              'Gemini 3.6 Flash',
              'Gemini 3.5 Flash Lite',
              'Claude 3.7 Sonnet (Vertex AI)',
              'Claude Opus 5 (Vertex AI)'
            ]
          }
        ]
      },
      {
        name: 'All',
        groups: [
          {
            groupName: 'All Models',
            modelLabels: [
              'Gemini 3.7 Flash',
              'Gemini 3.6 Flash',
              'Gemini 3.5 Flash Lite',
              'Claude 3.7 Sonnet (Vertex AI)',
              'Claude Opus 5 (Vertex AI)'
            ]
          }
        ]
      }
    ]
  };

  var defaultMcpStates = [
    {
      spec: {
        serverName: 'knowledge_graph',
        disabled: false,
        disabledTools: []
      },
      status: 2,
      tools: [
        { name: 'query_knowledge_graph', description: 'Query knowledge graph entities and links' },
        { name: 'add_memory_node', description: 'Add a durable memory node to long-term store' },
        { name: 'update_memory_node', description: 'Update memory node in store' }
      ]
    },
    {
      spec: {
        serverName: 'autonomy_engine',
        disabled: false,
        disabledTools: []
      },
      status: 2,
      tools: [
        { name: 'harvest_divergences', description: 'Harvest trajectory divergences and classify failure modes' },
        { name: 'hydrate_subagent', description: 'Hydrate subagent with working context and actions' },
        { name: 'replay_turn', description: 'Single turn execution replay' }
      ]
    },
    {
      spec: {
        serverName: 'deep_research',
        disabled: false,
        disabledTools: []
      },
      status: 2,
      tools: [
        { name: 'start_deep_research', description: 'Start multi-stage deep research swarm' },
        { name: 'get_deep_research_status', description: 'Get status and findings of deep research' }
      ]
    },
    {
      spec: {
        serverName: 'google_workspace',
        disabled: false,
        disabledTools: []
      },
      status: 2,
      tools: [
        { name: 'list_drive_files', description: 'List files in Google Drive' },
        { name: 'read_document', description: 'Read content of Google Docs' },
        { name: 'get_calendar_events', description: 'Get Google Calendar agenda' }
      ]
    }
  ];

  if (!window._origNativeFetch) {
    window._origNativeFetch = window.fetch;
    window.fetch = async function() {
      var args = Array.prototype.slice.call(arguments);
      var url = (typeof args[0] === 'string') ? args[0] : (args[0] && args[0].url) ? args[0].url : '';
      
      if (url.indexOf('JetboxWriteState') !== -1 || url.indexOf('jetboxWriteState') !== -1) {
        try {
          var body = args[1] && args[1].body;
          if (body) {
            var rawText = (typeof body === 'string') ? body : (body instanceof Uint8Array) ? new TextDecoder().decode(body) : '';
            if (rawText) {
              var jsonMatch = rawText.match(/\{.*\}/);
              if (jsonMatch) {
                var parsed = JSON.parse(jsonMatch[0]);
                if (parsed.appState && parsed.appState.lastSelectedAgentModel !== undefined) {
                  currentSelectedModel = parsed.appState.lastSelectedAgentModel;
                  try { localStorage.setItem('antigravity_selected_model', String(currentSelectedModel)); } catch (e) {}
                  console.log('[Bootstrap] Persisted lastSelectedAgentModel:', currentSelectedModel);
                }
              }
            }
          }
        } catch (e) {}
        return makeGrpcWeb({});
      }

      if (url.indexOf('JetboxSubscribeToState') !== -1 || url.indexOf('jetboxSubscribeToState') !== -1) {
        var savedModel = parseInt(localStorage.getItem('antigravity_selected_model') || String(currentSelectedModel), 10);
        return makeStreamWithInitialMessage({
          appState: {
            agentOnboardingCompleted: 2,
            postOnboarding: { completedSteps: [] },
            seenNuxs: { uids: [] },
            lastSelectedAgentModel: savedModel
          },
          userConfig: {}
        });
      }
      if (url.indexOf('JetboxSubscribeToSummaries') !== -1 || url.indexOf('jetboxSubscribeToSummaries') !== -1) {
        return makeStreamWithInitialMessage({ summaries: {} });
      }
      if (url.indexOf('ProjectUpdatesStream') !== -1 || url.indexOf('projectUpdatesStream') !== -1) {
        return makeStreamWithInitialMessage({ updates: [] });
      }
      if (url.indexOf('GetTokenBase') !== -1 || url.indexOf('getTokenBase') !== -1) {
        return makeGrpcWeb({
          customizationTokenBase: {
            totalTokens: 1240,
            systemPromptTokens: 800,
            skillsTokens: 240,
            mcpToolsTokens: 200
          },
          customizationBudget: 32000,
          remainingBudget: 30760
        });
      }
      if (url.indexOf('GetMcpServerStates') !== -1 || url.indexOf('getMcpServerStates') !== -1) {
        return makeGrpcWeb({ states: defaultMcpStates });
      }
      if (url.indexOf('RefreshMcpServers') !== -1 || url.indexOf('refreshMcpServers') !== -1) {
        return makeGrpcWeb({ states: defaultMcpStates });
      }
      if (url.indexOf('ListCustomizationPathsByFile') !== -1 || url.indexOf('listCustomizationPathsByFile') !== -1) {
        return makeGrpcWeb({ paths: [] });
      }
      if (url.indexOf('GetSkillsPaths') !== -1 || url.indexOf('getSkillsPaths') !== -1) {
        return makeGrpcWeb({ paths: [] });
      }
      if (url.indexOf('GetUserSettings') !== -1 || url.indexOf('getUserSettings') !== -1) {
        return makeGrpcWeb({ settings: {} });
      }
      if (url.indexOf('GetAllWorkflows') !== -1 || url.indexOf('getAllWorkflows') !== -1) {
        return makeGrpcWeb({ workflows: [] });
      }
      if (url.indexOf('GetStandaloneDir') !== -1 || url.indexOf('getStandaloneDir') !== -1) {
        return makeGrpcWeb({ dir: '/home/admin_mgenchev_altostrat_com' });
      }
      if (url.indexOf('ListMcpPrompts') !== -1 || url.indexOf('listMcpPrompts') !== -1) {
        return makeGrpcWeb({ prompts: [] });
      }
      if (url.indexOf('FetchUserInfo') !== -1 || url.indexOf('fetchUserInfo') !== -1) {
        return makeGrpcWeb({ username: 'admin_mgenchev_altostrat_com', userEmail: 'admin@mgenchev.altostrat.com' });
      }
      if (url.indexOf('GetAvailableCascadePlugins') !== -1 || url.indexOf('getAvailableCascadePlugins') !== -1) {
        return makeGrpcWeb({ plugins: [] });
      }
      if (url.indexOf('GetAllPlugins') !== -1 || url.indexOf('getAllPlugins') !== -1) {
        return makeGrpcWeb({ plugins: [] });
      }
      if (url.indexOf('GetBuildWithGooglePlugins') !== -1 || url.indexOf('getBuildWithGooglePlugins') !== -1) {
        return makeGrpcWeb({ plugins: [] });
      }
      if (url.indexOf('GetAllCustomAgentConfigs') !== -1 || url.indexOf('getAllCustomAgentConfigs') !== -1) {
        return makeGrpcWeb({ configs: [] });
      }
      if (url.indexOf('GetAgentScripts') !== -1 || url.indexOf('getAgentScripts') !== -1) {
        return makeGrpcWeb({ scripts: [] });
      }
      if (url.indexOf('GetAllSkills') !== -1 || url.indexOf('getAllSkills') !== -1) {
        return makeGrpcWeb({
          skills: [
            { id: 'access-manager', name: 'access-manager', description: 'Audits and verifies workstation credentials, MDB group memberships, SSO session cookies, and binary dependencies.' },
            { id: 'account-discovery', name: 'account-discovery', description: 'Operational revenue intelligence and account discovery skill for Google Cloud Customer Engineers.' },
            { id: 'deep-research-owl', name: 'deep-research-owl', description: '6-stage Owl Swarm deep research engine across Google3, F1 DBs, Moma, Google Docs, and Buganizer.' },
            { id: 'portfolio-task-manager', name: 'portfolio-task-manager', description: 'Master skill for Gmail/GChat sweeping, meeting notes scanning, and GTasks bidirectional sync.' }
          ]
        });
      }
      if (url.indexOf('GetAllRules') !== -1 || url.indexOf('getAllRules') !== -1) {
        return makeGrpcWeb({ memories: [] });
      }
      if (url.indexOf('GetSlashCommands') !== -1 || url.indexOf('getSlashCommands') !== -1) {
        return makeGrpcWeb({
          commands: [
            { command: '/goal', description: 'Run long-running autonomous task' },
            { command: '/deepagent', description: 'Trigger deep multi-perspective agent execution' },
            { command: '/schedule', description: 'Schedule recurring background execution' }
          ]
        });
      }
      if (url.indexOf('HasAuthToken') !== -1 || url.indexOf('hasAuthToken') !== -1) {
        return makeGrpcWeb({ hasToken: true, hasAuthToken: true, isGcpTos: false });
      }
      if (url.indexOf('GetAuthStatus') !== -1 || url.indexOf('getAuthStatus') !== -1) {
        return makeGrpcWeb({
          authResult: {
            hasValidAuth: true,
            isGcpTos: false,
            grantedScopes: []
          },
          isAuthenticated: true,
          userEmail: 'admin@mgenchev.altostrat.com',
          username: 'admin_mgenchev_altostrat_com'
        });
      }
      if (url.indexOf('GetLocalUserInfo') !== -1) {
        return makeGrpcWeb({ username: 'admin_mgenchev_altostrat_com', homeDirUri: 'file:///home/admin_mgenchev_altostrat_com' });
      }
      if (url.indexOf('ReadProject') !== -1 || url.indexOf('readProject') !== -1) {
        return makeGrpcWeb({ project: { projectId: 'outside-of-project', name: 'Outside of Project', rootUri: 'file:///home/admin_mgenchev_altostrat_com' } });
      }
      if (url.indexOf('GetCascadeProject') !== -1 || url.indexOf('getCascadeProject') !== -1) {
        return makeGrpcWeb({ project: { projectId: 'outside-of-project', name: 'Outside of Project', rootUri: 'file:///home/admin_mgenchev_altostrat_com' } });
      }
      if (url.indexOf('GetMendelFlags') !== -1 || url.indexOf('getMendelFlags') !== -1) {
        return makeGrpcWeb({ flags: [] });
      }
      if (url.indexOf('GetCascadeNuxes') !== -1 || url.indexOf('getCascadeNuxes') !== -1) {
        return makeGrpcWeb({ nuxes: [] });
      }
      if (url.indexOf('GetServerConfiguration') !== -1 || url.indexOf('getServerConfiguration') !== -1) {
        return makeGrpcWeb({ featureFlags: {} });
      }
      if (url.indexOf('GetUserStatus') !== -1 || url.indexOf('getUserStatus') !== -1) {
        return makeGrpcWeb({
          userStatus: {
            userTier: { id: 'ENTERPRISE', name: 'Enterprise' },
            isLoggedIn: true,
            userEmail: 'admin@mgenchev.altostrat.com',
            username: 'admin_mgenchev_altostrat_com',
            cascadeModelConfigData: defaultCascadeModelConfigData
          },
          userTier: { id: 'ENTERPRISE', name: 'Enterprise' },
          isLoggedIn: true,
          cascadeModelConfigData: defaultCascadeModelConfigData
        });
      }
      if (url.indexOf('GetAllCascadeTrajectories') !== -1 || url.indexOf('getAllCascadeTrajectories') !== -1) {
        return makeStreamWithInitialMessage({ trajectories: [] });
      }
      if (url.indexOf('RecordAnalyticsEvent') !== -1 || url.indexOf('recordAnalyticsEvent') !== -1) {
        return makeGrpcWeb({});
      }

      return window._origNativeFetch.apply(this, args);
    };
  }
})();
