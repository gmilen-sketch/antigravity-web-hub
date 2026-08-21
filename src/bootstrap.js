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
        modelOrAlias: { choice: { case: 'alias', value: 'gemini-3.7-flash' } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Recommended',
        tagDescription: 'High-speed reasoning and code generation',
        supportsThoughtCirculation: true
      },
      {
        label: 'Gemini 3.5 Pro',
        modelOrAlias: { choice: { case: 'alias', value: 'gemini-3.5-pro' } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Complex Reasoning',
        tagDescription: 'Deep architectural synthesis',
        supportsThoughtCirculation: true
      },
      {
        label: 'Gemini 3.5 Flash',
        modelOrAlias: { choice: { case: 'alias', value: 'gemini-3.5-flash' } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'High-Throughput',
        tagDescription: 'Low-latency processing',
        supportsThoughtCirculation: true
      }
    ],
    defaultOverrideModelConfig: {
      label: 'Gemini 3.7 Flash',
      modelOrAlias: { choice: { case: 'alias', value: 'gemini-3.7-flash' } }
    }
  };

  if (!window._origNativeFetch) {
    window._origNativeFetch = window.fetch;
    window.fetch = async function() {
      var args = Array.prototype.slice.call(arguments);
      var url = (typeof args[0] === 'string') ? args[0] : (args[0] && args[0].url) ? args[0].url : '';
      
      if (url.indexOf('JetboxSubscribeToState') !== -1 || url.indexOf('jetboxSubscribeToState') !== -1) {
        return makeStreamWithInitialMessage({
          appState: {
            agentOnboardingCompleted: 2,
            postOnboarding: { completedSteps: [] },
            seenNuxs: { uids: [] },
            lastSelectedAgentModel: 0
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
        return makeGrpcWeb({ trajectories: [] });
      }
      if (url.indexOf('RecordAnalyticsEvent') !== -1 || url.indexOf('recordAnalyticsEvent') !== -1) {
        return makeGrpcWeb({});
      }
      if (url.indexOf('GetAllSkills') !== -1 || url.indexOf('getAllSkills') !== -1) {
        return makeGrpcWeb({ skills: [] });
      }
      if (url.indexOf('GetSlashCommands') !== -1 || url.indexOf('getSlashCommands') !== -1) {
        return makeGrpcWeb({ commands: [] });
      }
      if (url.indexOf('GetMcpServerStates') !== -1 || url.indexOf('getMcpServerStates') !== -1) {
        return makeGrpcWeb({ servers: [] });
      }

      return window._origNativeFetch.apply(this, args);
    };
  }
})();
