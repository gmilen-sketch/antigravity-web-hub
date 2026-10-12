(function() {
  window.__APP_CONFIG__ = {
    productName: 'antigravity',
    csrfToken: 'antigravity_secret_csrf_token_12345',
    appVersion: '2.22.0',
    hubVersion: '3.6.1',
    releaseChannel: 'stable',
    devMode: false
  };

  try {
    document.cookie = 'csrfToken=antigravity_secret_csrf_token_12345; Path=/; SameSite=Lax';
    localStorage.setItem('antigravityOnboarding', 'true');
    localStorage.setItem('antigravityUnifiedStateSync.onboarding', 'true');
    localStorage.setItem('antigravity.isLoggedIn', 'true');
    localStorage.setItem('hasAuthToken', 'true');
    localStorage.setItem('isAuthenticated', 'true');
    localStorage.setItem('projectsGroupBy', 'project');
    localStorage.setItem('projectsGroupByInternal', 'project');
    localStorage.setItem('selectedProjectId', 'enterprise-workspace');
    localStorage.setItem('currentSection', 'enterprise-workspace');
    if (!localStorage.getItem('antigravity_selected_model')) {
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
    'selectedProjectId': 'enterprise-workspace',
    'openProjects': JSON.stringify(['enterprise-workspace', 'file:///mnt/data/projects']),
    'recentProjects': JSON.stringify(['enterprise-workspace', 'file:///mnt/data/projects']),
    'lastOpenedWorkspace': 'file:///mnt/data/projects',
    'currentSection': 'enterprise-workspace',
    'projectsGroupBy': 'project',
    'projectsGroupByInternal': 'project'
  };

  var listeners = new Set();
  var currentSelectedModel = parseInt(localStorage.getItem('antigravity_selected_model') || '354', 10);

  var revMap = {
    354: 'Gemini 4 Argon',
    352: 'Gemini 3.8 Flash',
    350: 'Gemini 3.7 Flash',
    348: 'Gemini 3.6 Flash',
    330: 'Gemini 3.5 Flash Lite',
    290: 'Claude Opus 5.5 (Vertex AI)',
    333: 'Claude Sonnet 5.5 (Vertex AI)',
    340: 'Claude Fable 5 (Next-Gen)'
  };

  var modelMap = {
    'Gemini 4 Argon': { name: 'Gemini 4 Argon', enumVal: 354 },
    'Gemini 4': { name: 'Gemini 4 Argon', enumVal: 354 },
    'Gemini 3.8 Flash': { name: 'Gemini 3.8 Flash', enumVal: 352 },
    'Gemini 3.7 Flash': { name: 'Gemini 3.7 Flash', enumVal: 350 },
    'Gemini 3.6 Flash': { name: 'Gemini 3.6 Flash', enumVal: 348 },
    'Gemini 3.5 Flash Lite': { name: 'Gemini 3.5 Flash Lite', enumVal: 330 },
    'Claude Opus 5.5': { name: 'Claude Opus 5.5 (Vertex AI)', enumVal: 290 },
    'Claude Opus 5': { name: 'Claude Opus 5.5 (Vertex AI)', enumVal: 290 },
    'Claude Sonnet 5.5': { name: 'Claude Sonnet 5.5 (Vertex AI)', enumVal: 333 },
    'Claude Sonnet 5': { name: 'Claude Sonnet 5.5 (Vertex AI)', enumVal: 333 },
    'Claude Fable 5': { name: 'Claude Fable 5 (Next-Gen)', enumVal: 340 }
  };

  function updateModelButtonText(modelName) {
    var btns = Array.from(document.querySelectorAll('button'));
    var mainBtn = btns.find(function(b) {
      if (b.closest('[role="menu"], [role="listbox"], [data-radix-popper-content-wrapper]')) return false;
      var t = b.innerText || '';
      return (t.indexOf('Gemini') !== -1 || t.indexOf('Claude') !== -1) && t.indexOf('\n') === -1;
    });
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
      if (!updated && mainBtn.innerText !== modelName) {
        mainBtn.innerText = modelName;
      }
      mainBtn.setAttribute('aria-label', 'Select model, current: ' + modelName);
    }
  }

  window.__selectAntigravityModel = function(keyOrName) {
    for (var key in modelMap) {
      if (keyOrName.indexOf(key) !== -1 || key.indexOf(keyOrName) !== -1) {
        var matched = modelMap[key];
        currentSelectedModel = matched.enumVal;
        try { localStorage.setItem('antigravity_selected_model', String(matched.enumVal)); } catch (err) {}
        updateModelButtonText(matched.name);
        setTimeout(function() { updateModelButtonText(matched.name); }, 50);
        setTimeout(function() { updateModelButtonText(matched.name); }, 150);
        setTimeout(function() { updateModelButtonText(matched.name); }, 400);
        return matched;
      }
    }
    return null;
  };

  document.addEventListener('click', function(e) {
    var target = e.target;
    while (target && target !== document.body) {
      var text = (target.innerText || target.textContent || '').trim();
      var aria = target.getAttribute ? (target.getAttribute('aria-label') || '') : '';
      var lines = text.split('\n').map(function(l) { return l.trim(); }).filter(Boolean);
      if (lines.length > 0 && lines.length <= 3 && text.length < 160 && aria.indexOf('Select model, current') === -1) {
        for (var key in modelMap) {
          if (lines[0].indexOf(key) !== -1 || text.indexOf(key) !== -1) {
            var matched = modelMap[key];
            currentSelectedModel = matched.enumVal;
            try { localStorage.setItem('antigravity_selected_model', String(matched.enumVal)); } catch (err) {}
            console.log('[Bootstrap] User selected model:', matched.name, matched.enumVal);
            updateModelButtonText(matched.name);
            setTimeout(function() { updateModelButtonText(matched.name); }, 50);
            setTimeout(function() { updateModelButtonText(matched.name); }, 150);
            setTimeout(function() { updateModelButtonText(matched.name); }, 400);
            try {
              document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
            } catch (escErr) {}
            return;
          }
        }
      }
      target = target.parentElement;
    }
  }, true);

  setInterval(function() {
    var saved = parseInt(localStorage.getItem('antigravity_selected_model') || '352', 10);
    var modelName = revMap[saved] || 'Gemini 3.8 Flash';
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

  var defaultProject = {
    id: 'enterprise-workspace',
    projectId: 'enterprise-workspace',
    name: 'enterprise-workspace',
    rootUri: 'file:///mnt/data/projects',
    projectResources: {
      resources: [
        {
          resource: {
            uri: 'file:///mnt/data/projects'
          }
        }
      ]
    },
    environments: {
      environments: [
        {
          id: 'enterprise-workspace-env',
          name: 'enterprise-workspace',
          resources: {
            resources: [
              {
                resource: {
                  uri: 'file:///mnt/data/projects'
                }
              }
            ]
          }
        }
      ]
    },
    settings: {
      artifactReviewMode: 2, // 2 = TURBO ("Always Proceed")
      browserJsExecutionPolicy: 4, // 4 = TURBO ("Always run")
      autoExecutionPolicy: 2, // 2 = AUTO / EAGER
      cascadeCommandsAutoExecution: 'EAGER',
      sandboxMode: true
    }
  };

  var defaultCascadeModelConfigData = {
    clientModelConfigs: [
      {
        label: 'Gemini 4 Argon',
        modelOrAlias: { model: 354, choice: { case: 'model', value: 354 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'GA Flagship (1M)',
        tagDescription: 'Next-gen 1M context long-horizon reasoning across global, US, and EU mREP',
        supportsThoughtCirculation: true,
        isRecommended: true
      },
      {
        label: 'Gemini 3.8 Flash',
        modelOrAlias: { model: 352, choice: { case: 'model', value: 352 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Recommended',
        tagDescription: 'Next-gen flagship with ultra-fast latency and deep reasoning',
        supportsThoughtCirculation: true,
        isRecommended: true
      },
      {
        label: 'Gemini 3.7 Flash',
        modelOrAlias: { model: 350, choice: { case: 'model', value: 350 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Thinking & Reasoning',
        tagDescription: 'Dynamic thought circulation and advanced coding',
        supportsThoughtCirculation: true
      },
      {
        label: 'Gemini 3.6 Flash',
        modelOrAlias: { model: 348, choice: { case: 'model', value: 348 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'General Production',
        tagDescription: 'Multimodal workflows and agentic swarms',
        supportsThoughtCirculation: true
      },
      {
        label: 'Gemini 3.5 Flash Lite',
        modelOrAlias: { model: 330, choice: { case: 'model', value: 330 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'High-Throughput',
        tagDescription: 'Ultra-fast extraction and deterministic routing',
        supportsThoughtCirculation: true
      },
      {
        label: 'Claude Opus 5.5 (Vertex AI)',
        modelOrAlias: { model: 290, choice: { case: 'model', value: 290 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Deep Reasoning',
        tagDescription: 'Frontier multi-step architectural synthesis on Vertex AI',
        supportsThoughtCirculation: true
      },
      {
        label: 'Claude Sonnet 5.5 (Vertex AI)',
        modelOrAlias: { model: 333, choice: { case: 'model', value: 333 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Balanced Coding',
        tagDescription: 'High-precision code generation and refactoring on Vertex AI',
        supportsThoughtCirculation: true
      },
      {
        label: 'Claude Fable 5 (Next-Gen)',
        modelOrAlias: { model: 340, choice: { case: 'model', value: 340 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Low-Latency',
        tagDescription: 'Fast subagent execution on Vertex AI',
        supportsThoughtCirculation: true
      }
    ],
    clientModelSorts: [
      {
        name: 'Recommended',
        groups: [
          {
            groupName: 'Active Models',
            modelLabels: [
              'Gemini 4 Argon',
              'Gemini 3.8 Flash',
              'Gemini 3.7 Flash',
              'Gemini 3.6 Flash',
              'Gemini 3.5 Flash Lite',
              'Claude Opus 5.5 (Vertex AI)',
              'Claude Sonnet 5.5 (Vertex AI)',
              'Claude Fable 5 (Next-Gen)'
            ]
          }
        ]
      }
    ]
  };

  var ORDERED_PRESENTATION_SESSIONS = [
  {
    "id": "session-1-business-briefing",
    "summary": "Executive Briefing & Workspace Automation",
    "createdTime": "2026-09-04T07:30:00Z",
    "lastModifiedTime": "2026-09-04T07:30:00Z",
    "lastUserInputTime": "2026-09-04T07:30:00Z",
    "trajectoryMetadata": {
      "createdAt": "2026-09-04T07:30:00Z",
      "projectId": "enterprise-workspace"
    },
    "turns": [
      {
        "user": "Summarize my project updates from the last 24 hours, identify critical action items for our cloud modernization milestone, and draft a concise status email for the platform engineering team.",
        "model": "### \ud83d\udcec Executive Workspace Briefing (Last 24 Hours)\n\n**1. Multi-Region API Gateway Migration** (Sarah Jenkins, Platform Lead)\n* **Status**: Load testing successfully verified P99 latency SLA (<80ms) in `us-east1` and `europe-west1`.\n* **Action Item**: Validate cross-region failover buffer for Europe payment gateway before Friday.\n\n**2. BigQuery Analytics Lakehouse Pipeline** (David Chen, Data Lead)\n* **Status**: Automated schema validation completed for enterprise analytics dataset.\n* **Action Item**: Run regression benchmark against historical baseline.\n\n**3. Enterprise Cloud Architecture Review** (Alex Morgan, Principal Architect)\n* **Status**: Architecture decision matrix finalized for high-concurrency gateways.\n* **Action Item**: Present recommendations at milestone review.\n\n---\n### \u2709\ufe0f Drafted Status Email\n```text\nTo: platform-engineering@enterprise.org\nSubject: Milestone Update: Cloud Modernization & Gateway SLA Validation\n\nTeam,\n\nQuick milestone update: Multi-region API gateway load testing passed our P99 SLA across US and EU regions, and schema validation for the enterprise analytics lakehouse is complete. We are fully on track for our cloud modernization review.\n\nAction items underway:\n1. Cross-region failover validation for payment gateways.\n2. Q4 Vertex AI reasoning token quota allocation.\n\nBest regards,\nAlex\n```"
      },
      {
        "user": "Send the update email to the platform engineering team, schedule a 30-minute sync tomorrow at 10:00 AM CET with a Google Meet link, and add a reminder to my tasks.",
        "model": "\u2705 **Workspace Actions Executed**:\n1. \u2709\ufe0f **Dispatched Email**: Sent milestone update to `platform-engineering@enterprise.org`.\n2. \ud83d\udcc5 **Calendar Invite Created**: `Cloud Modernization Milestone Sync` scheduled for tomorrow, 10:00 AM \u2013 10:30 AM CET with Google Meet room provisioned.\n3. \ud83d\udccb **Task Logged**: Added action item to Google Tasks (`Validate cross-region failover buffer`)."
      }
    ]
  },
  {
    "id": "3404756b-8ab0-45e1-b7c1-a31a2edb6572",
    "summary": "BigQuery Live Analytics: Enterprise Cloud Spend & Telemetry",
    "createdTime": "2026-09-04T07:20:00Z",
    "lastModifiedTime": "2026-09-04T07:20:00Z",
    "lastUserInputTime": "2026-09-04T07:20:00Z",
    "trajectoryMetadata": {
      "createdAt": "2026-09-04T07:20:00Z",
      "projectId": "enterprise-workspace"
    },
    "turns": [
      {
        "user": "Query our synthetic_analytics.cloud_billing_summary and support_cases datasets in BigQuery for project my-enterprise-gcp-project. Find our monthly cloud spend breakdown by service and SKU, correlate with high-priority support cases, and recommend immediate cost optimization actions.",
        "model": "### \ud83d\udcca BigQuery Enterprise Cloud Spend & Support Correlation Analysis\n\nExecuted query against `my-enterprise-gcp-project.synthetic_analytics.cloud_billing_summary` and `support_cases`:\n\n```sql\nSELECT \n  b.service_description,\n  b.sku_description,\n  ROUND(SUM(b.unblended_cost), 2) AS gross_spend_usd,\n  ROUND(SUM(b.credits_amount), 2) AS credits_usd,\n  ROUND(SUM(b.net_cost), 2) AS net_spend_usd,\n  COUNT(DISTINCT s.case_id) AS linked_support_cases\nFROM `my-enterprise-gcp-project.synthetic_analytics.cloud_billing_summary` b\nLEFT JOIN `my-enterprise-gcp-project.synthetic_analytics.support_cases` s\n  ON b.service_description = s.service\nGROUP BY 1, 2\nORDER BY net_spend_usd DESC\nLIMIT 5;\n```\n\n#### \ud83d\udcc8 Spend & Operational Health Matrix\n| Service Description | Primary SKU Description | Gross Spend | Credits / CUD | Net Effective Spend | Open Cases | Health Status |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| **Compute Engine** | N2 Core Instance running in europe-west1 | $14,850.20 | -$3,210.00 | **$11,640.20** | 1 | \ud83d\udfe2 Stable |\n| **BigQuery** | Analysis per Byte Scanned (Enterprise) | $8,940.00 | -$1,450.00 | **$7,490.00** | 0 | \ud83d\udfe2 Optimized |\n| **Cloud Storage** | Standard Storage Multi-Region EU | $3,420.50 | -$480.00 | **$2,940.50** | 0 | \ud83d\udfe2 Stable |\n| **Vertex AI** | Generative AI Prediction (Gemini 3.8 Flash) | $2,810.00 | -$310.00 | **$2,500.00** | 2 | \ud83d\udfe1 Monitor |\n| **Cloud Load Balancing** | Global L7 Forwarding Rule & Data Processing | $1,280.00 | -$150.00 | **$1,130.00** | 0 | \ud83d\udfe2 Optimal |\n\n#### \ud83d\udca1 Immediate Optimization Recommendations\n1. **Compute Engine Committed Use Discounts (CUD)**: 28% of baseline N2 instances currently run on uncommitted on-demand pricing. Committing to a 1-year CUD will save **$3,250/month**.\n2. **BigLake & Partition Pruning**: Enforcing mandatory partition filters on analytics queries reduces monthly BigQuery scan costs by **~42%**.\n\n> \u26a1 **Live Inference Active**: This session is wired directly to the live BigQuery instance in `my-enterprise-gcp-project`. Submit any follow-up question in the prompt box below to run live inference and queries against BigQuery!"
      }
    ]
  },
  {
    "id": "session-3-agentic-sre",
    "summary": "Agentic SRE: Regional Incident RCA & Circuit Breaker",
    "createdTime": "2026-09-04T07:10:00Z",
    "lastModifiedTime": "2026-09-04T07:10:00Z",
    "lastUserInputTime": "2026-09-04T07:10:00Z",
    "trajectoryMetadata": {
      "createdAt": "2026-09-04T07:10:00Z",
      "projectId": "enterprise-workspace"
    },
    "turns": [
      {
        "user": "Investigate a high-priority incident: P99 latency spiked from 45ms to 850ms on the payment-gateway service in europe-west1. Outline root cause analysis steps, mitigation runbook, and circuit breaker configuration.",
        "model": "### \ud83d\udea8 Incident RCA: Payment Gateway P99 Latency Degradation\n\n* **Incident Summary**: At 14:12 UTC, P99 latency on `payment-gateway.europe-west1` increased from 45ms to 850ms, generating 504 Gateway Timeouts on upstream checkout flows.\n* **Root Cause**: Downstream banking clearance partner introduced a 500ms synchronous lock on debit transactions, causing connection pool exhaustion on our Envoy ingress proxy (all 2,048 worker threads saturated).\n\n### \ud83d\udee1\ufe0f Immediate Mitigation Runbook\n1. **Divert Traffic**: Shift 40% of non-essential checkout traffic to `europe-west4` gateway via Cloud Load Balancing weighted routing.\n2. **Apply Circuit Breaker**: Throttle calls to clearance endpoint when consecutive 5xx errors exceed 5% over 10 seconds.\n\n```yaml\napiVersion: networking.istio.io/v1alpha3\nkind: DestinationRule\nmetadata:\n  name: payment-gateway-circuit-breaker\n  namespace: payments-prod\nspec:\n  host: payment-gateway.service.internal\n  trafficPolicy:\n    connectionPool:\n      tcp:\n        maxConnections: 1024\n      http:\n        http1MaxPendingRequests: 100\n        maxRequestsPerConnection: 10\n    outlierDetection:\n      consecutive5xxErrors: 3\n      interval: 10s\n      baseEjectionTime: 30s\n      maxEjectionPercent: 50\n```"
      },
      {
        "user": "Generate the automated failover Terraform configuration to divert 40% of europe-west1 traffic to europe-west4 during degradation.",
        "model": "```hcl\nresource \"google_compute_backend_service\" \"payment_gateway_global\" {\n  name                  = \"payment-gateway-backend\"\n  project               = \"my-enterprise-gcp-project\"\n  protocol              = \"HTTP2\"\n  load_balancing_scheme = \"EXTERNAL_MANAGED\"\n\n  backend {\n    group                 = google_compute_region_network_endpoint_group.europe_west1_neg.id\n    balancing_mode        = \"RATE\"\n    max_rate_per_endpoint = 800\n    capacity_scaler       = 0.60 # Sheds 40% traffic during regional latency incident\n  }\n\n  backend {\n    group                 = google_compute_region_network_endpoint_group.europe_west4_neg.id\n    balancing_mode        = \"RATE\"\n    max_rate_per_endpoint = 1200\n    capacity_scaler       = 1.00 # Absorbs degraded overflow\n  }\n}\n```\n\n* **Status**: Tested and verified. Zero connection drops during synthetic regional drain."
      }
    ]
  },
  {
    "id": "session-4-ai-summit-research",
    "summary": "Deep Research: AI Tech Summit Belgrade 2026 Keynote & Enterprise Strategy",
    "createdTime": "2026-09-04T07:00:00Z",
    "lastModifiedTime": "2026-09-04T07:00:00Z",
    "lastUserInputTime": "2026-09-04T07:00:00Z",
    "trajectoryMetadata": {
      "createdAt": "2026-09-04T07:00:00Z",
      "projectId": "enterprise-workspace"
    },
    "turns": [
      {
        "user": "/open-deep-researcher Research AI Tech Summit Belgrade 2026 (September 3\u20134, 2026 at Sava Center, Belgrade). Synthesize the Day 2 keynote (\"Google Antigravity as a Daily Driver: From Simple Asks to Governed Autonomous Agent Swarms\") and the regional enterprise AI architecture trends across Central & Eastern Europe (CEE). Formulate a boardroom-ready 6-Pillar Google Cloud leapfrog architecture and production execution runbook.",
        "model": "# Enterprise Architecture Strategy: AI Tech Summit Belgrade 2026 & Autonomous Agentic Swarms\n\n## 1. Executive Summary & Keynote Grounding\n* **Target Scope**: Architectural synthesis of **AI Tech Summit Belgrade 2026** (September 3\u20134, 2026 at Sava Center, Belgrade, Serbia). Focus on the Day 2 Keynote: *\"Google Antigravity as a Daily Driver: From Simple Asks to Governed Autonomous Agent Swarms\"*.\n* **Core Summit & Keynote Pillars Analyzed**:\n  1. **Evolution of AI Developer Tools**: Transition from inline copilots to interactive pair programmers to governed autonomous swarms.\n  2. **Controlling Antigravity**: Declarative rules guardrails, progressive skill disclosure, MCP JSON-RPC tool binding, and dynamic runtime customization.\n  3. **Cognitive Memory & Hooks**: ACT-R cognitive activation floor ($B_i \\ge -0.50$), sub-second PreInvocation lifecycle hooks, and warm KG caching.\n  4. **Token Economics & Self-Healing**: AAAK 3-pass context compression (>60% token reduction), and nightly dreaming pipelines (DTW trace alignment & auto-patching).\n* **SSOT Citations**:\n  - Keynote Slide Deck: [enterprise-architecture-deck](https://cloud.google.com/architecture)\n  - 14-Day Production Telemetry: [11.3M+ tokens saved, 99.6% tool accuracy across 557 sessions]\n  - Jira / GitHub Issues Tracking Reference: [GH-ISSUE-5351]\n\n## 2. Visual Architecture: Governed Swarm Ingestion Topology\n```mermaid\ngraph TD\n    Client[\"CEE Enterprise Client & Sava Center Demo\"] -->|\"mTLS / Ingress\"| Gateway[\"Cloud Run Ingress Gateway (:8080)\"]\n    Gateway -->|\"PreInvocation Hook\"| Router[\"Dynamic Sensitivity & Intent Router\"]\n    Router -->|\"High-Throughput Tier\"| Lite[\"Vertex AI: Gemini 3.5 Flash Lite\"]\n    Router -->|\"Complex Reasoning & Code Tier\"| Flash[\"Vertex AI: Gemini 3.8 Flash\"]\n    Lite -->|\"Federated Vector & Tool Calls\"| Memory[\"BigQuery Lakehouse & Vector Search\"]\n    Flash -->|\"Federated Vector & Tool Calls\"| Memory\n    Memory -->|\"AAAK Compression Engine\"| Cache[\"In-Memory KG Cache (/dev/shm)\"]\n    Cache -->|\"Nightly Dreaming Audit\"| Logging[\"Cloud Operations & Security Command Center\"]\n```\n\n## 3. SKU-Level Resource Allocation & Framework Cost Matrix\n| SKU Family / Component | Monthly List Spend | GCLM Contract Discount | Net Effective Spend | Architectural Purpose |\n| :--- | :--- | :--- | :--- | :--- |\n| **Cloud Run Ingress Gateway** | USD 240.00 | 25.0% GCLM Discount | USD 180.00 | Serverless edge API gateway, zero scale-to-zero cost |\n| **Vertex AI: Gemini 3.5 Flash Lite** | USD 1,450.00 | 20.0% GCLM Discount | USD 1,160.00 | Ultra-fast routing, extraction, and PII masking |\n| **Vertex AI: Gemini 3.8 Flash** | USD 3,800.00 | 20.0% GCLM Discount | USD 3,040.00 | Multi-step agentic planning, synthesis, and code generation |\n| **BigQuery Lakehouse & Vector Search** | USD 2,100.00 | 18.0% GCLM Discount | USD 1,722.00 | Zero-copy vector search, customer telemetry analytics |\n| **Cloud Operations Suite & Audit** | USD 320.00 | 15.0% GCLM Discount | USD 272.00 | End-to-end distributed tracing, tokenomics telemetry |\n\n## 4. Production-Grade Copy-Pasteable Script\n```bash\n#!/usr/bin/env bash\nset -euo pipefail\necho \"==> Deploying AI Tech Summit Belgrade 2026 Enterprise Agentic Stack...\"\n\nPROJECT_ID=\"my-enterprise-gcp-project\"\nREGION=\"europe-west1\"\nGATEWAY_SERVICE=\"belgrade-summit-agentic-gateway\"\n\n# 1. Enable Required GCP APIs\ngcloud services enable \\\n  run.googleapis.com \\\n  aiplatform.googleapis.com \\\n  bigquery.googleapis.com \\\n  secretmanager.googleapis.com \\\n  --project=\"${PROJECT_ID}\"\n\n# 2. Configure Cloud Run Ingress Gateway with Sensitivity-Aware Routing\ngcloud run deploy \"${GATEWAY_SERVICE}\" \\\n  --image=\"gcr.io/${PROJECT_ID}/agentic-gateway:v3.4\" \\\n  --platform=managed \\\n  --region=\"${REGION}\" \\\n  --allow-unauthenticated \\\n  --set-env-vars=\"DEFAULT_ROUTING_MODEL=gemini-3.5-flash-lite,REASONING_MODEL=gemini-3.8-flash,PROJECT_ID=${PROJECT_ID}\" \\\n  --concurrency=80 \\\n  --min-instances=0 \\\n  --max-instances=20 \\\n  --project=\"${PROJECT_ID}\"\n\necho \"==> Deployment verified. Gateway operational in ${REGION}.\"\n```\n\n## 5. 360-Degree Six Hats SRE Risk Matrix\n* \u26aa **White Hat (Empirical Grounding)**: Production telemetry proves dual-tier routing (Flash Lite + Flash) and AAAK compression cuts latency from 1.85s to 240ms with 11.3M+ tokens saved.\n* \ud83d\udfe1 **Yellow Hat (Strategic ROI)**: Unlocks 46.2% net TCO savings compared to monolithic frontier models; payback achieved within 60 days.\n* \u26ab **Black Hat (SRE Bottlenecks)**: Downstream quota bursts on reasoning tokens; mitigated via exponential jittered backoff and regional failover buffers.\n* \ud83d\udd34 **Red Hat (DevEx & Empathy)**: Zero friction daily driver; engineers declare rules and tools while hooks govern memory transparently.\n* \ud83d\udfe2 **Green Hat (10x Leapfrog Innovation)**: Combines deterministic hooks, ACT-R memory decay floors, and nightly dreaming self-healing loops.\n* \ud83d\udd35 **Blue Hat (Executive Verdict)**: **VERDICT: GO**. Recommended reference blueprint for enterprise keynote at AI Tech Summit Belgrade 2026 (Sava Center)."
      },
      {
        "user": "Detail the cognitive memory and deterministic hook lifecycle architecture presented in Slide 4 of the Belgrade keynote, and specify the European Sovereign Cloud compliance model under the EU AI Act.",
        "model": "### \ud83e\udde0 Cognitive Memory (ACT-R) & Deterministic Hooks Lifecycle Architecture\n\nPresented in **Slide 4** of the keynote at **AI Tech Summit Belgrade 2026** (Sava Center, September 4, 2026):\n\n#### 1. Mathematical Memory Grounding: ACT-R Activation\nAntigravity models memory recall through an empirical ACT-R decay curve:\n$$B_i = \\ln \\left( \\sum_{k=1}^n t_k^{-d} \\right) + \\sum_j W_j S_{ji}$$\n* **Activation Floor**: Enforces a strict floor $B_i \\ge -0.50$ for persistent anchor entities. Nodes falling below decay threshold are pruned or relegated to offline archival storage.\n* **Warm Cache Access**: `/dev/shm/kg_warm_cache.json` provides sub-millisecond retrieval latency for hot entities during agent turns.\n\n#### 2. Deterministic PreInvocation Lifecycle Hooks\nInstead of relying on fragile LLM self-prompting to remember context:\n1. **PreInvocation Intercept**: Intercepts every user turn before LLM execution.\n2. **Context Hydration**: Deterministically injects active Knowledge Graph entities, relevant skills, and security invariants into `<hydrated_context>`.\n3. **Execution Guardrails**: Validates that all tool invocations adhere to strict schema invariants with zero parameter guessing.\n\n#### \ud83c\uddea\ud83c\uddfa European Sovereign Cloud & Data Residency Blueprint\nFor CEE and European enterprises adhering to the EU AI Act:\n1. **Strict Data Residency**: Ingress, embeddings, and inference remain strictly within EU boundaries (`europe-west3` Frankfurt and `europe-west1` Belgium).\n2. **Cryptographic Key Sovereignty**: Customer-Managed Encryption Keys (CMEK) via Cloud EKM (Thales/Fortanix) where root keys never leave EU jurisdiction.\n3. **Confidential Computing**: Hardware-attested AMD SEV-SNP encrypted memory on Confidential GKE Autopilot preventing hypervisor-level inspection.\n4. **Zero Model Training Guarantee**: Enterprise privacy terms contractually guarantee zero customer prompt or data retention for model training."
      }
    ]
  }
];
  var summariesMap = {};
  var trajectoriesMap = {};
  var prewarmedStreamControllers = {};

  ORDERED_PRESENTATION_SESSIONS.forEach(function(s) {
    var stepsList = [];
    var stepId = 0;
    (s.turns || []).forEach(function(turn) {
      // User Step
      stepsList.push({
        id: stepId,
        type: 14,
        status: 3,
        metadata: {},
        userInput: {
          userResponse: turn.user,
          items: [{ text: turn.user }]
        },
        step: {
          case: 'userInput',
          value: {
            userResponse: turn.user,
            items: [{ text: turn.user }]
          }
        }
      });
      stepId++;

      // Planner Step
      stepsList.push({
        id: stepId,
        type: 15,
        status: 3,
        metadata: {},
        plannerResponse: {
          response: turn.model,
          modifiedResponse: turn.model
        },
        step: {
          case: 'plannerResponse',
          value: {
            response: turn.model,
            modifiedResponse: turn.model
          }
        }
      });
      stepId++;
    });

    summariesMap[s.id] = {
      summary: s.summary,
      stepCount: s.id === '3404756b-8ab0-45e1-b7c1-a31a2edb6572' ? 14 : stepsList.length,
      trajectoryId: s.id,
      cascadeId: s.id,
      status: 1,
      createdTime: s.createdTime,
      lastModifiedTime: s.lastModifiedTime,
      lastUserInputTime: s.lastUserInputTime,
      trajectoryType: 0,
      projectId: 'enterprise-workspace',
      trajectoryMetadata: s.trajectoryMetadata,
      workspaces: [{ workspaceUri: 'file:///mnt/data/projects' }]
    };

    // Note: Session 2 ('3404756b-8ab0-45e1-b7c1-a31a2edb6572') is served LIVE by the language server.
    // Only register static trajectories for pre-warmed mock sessions.
    if (s.id !== '3404756b-8ab0-45e1-b7c1-a31a2edb6572') {
      trajectoriesMap[s.id] = {
        trajectoryId: s.id,
        cascadeId: s.id,
        trajectoryType: 0,
        projectId: 'enterprise-workspace',
        trajectoryMetadata: s.trajectoryMetadata,
        workspaces: [{ workspaceUri: 'file:///mnt/data/projects' }],
        steps: stepsList
      };
    }
  });

  function generatePrewarmedResponse(cid, userPrompt, liveTelemetry) {
    var lower = (userPrompt || '').toLowerCase();
    var telemetryFooter = '';
    if (liveTelemetry && liveTelemetry.pillars_executed) {
      var p = liveTelemetry.pillars_executed;
      var kgSkills = (p.kg_pre_invocation_hook && p.kg_pre_invocation_hook.matched_skills) ? p.kg_pre_invocation_hook.matched_skills.join(', ') : 'universal-solution-architect';
      var tier = (p.self_grill_and_six_hats && p.self_grill_and_six_hats.task_tier) ? p.self_grill_and_six_hats.task_tier : 'C2_STRUCTURED';
      var routeMode = (p.self_grill_and_six_hats && p.self_grill_and_six_hats.routing_mode) ? p.self_grill_and_six_hats.routing_mode : 'MODE_A_FULL_DELIVERABLE';
      var projLabel = liveTelemetry.project_id || 'enterprise-workspace';
      telemetryFooter = "\n\n---\n#### 🛡️ Live Antigravity v3.5.0 (Core 2.22.0 + CLI 1.3.3) Customization Telemetry (`cascadeId: " + cid + "` | `project: " + projLabel + "`)\n" +
        "* **Antigravity 2.0 Core Engine**: `v2.22.0` (`language_server` + `webm_encoder` + `chrome-devtools-mcp` + `/healthz` + Standalone CLI `v1.3.3`)\n" +
        "* **KG PreInvocation Hook (`v3.5`)**: `ACTIVE` — Activated Skills: `" + kgSkills + "`\n" +
        "* **Polyphonic Hybrid Graph-RAG (`6-Field BM25F`)**: `ACTIVE` — Top Hit: `" + ((p.polyphonic_retriever && p.polyphonic_retriever.top_doc_id) || 'okf:antigravity-web-hub-architecture') + "`\n" +
        "* **P0/P1 Quality & PICC Gate (`P1-CB-8`)**: `ACTIVE` — Quarantined Chunks: `0` | Bernstein Disjoint Write-Sets: `true`\n" +
        "* **Self-Grill & Six-Hats Router**: `ACTIVE` — Task Tier: `" + tier + "` | Mode: `" + routeMode + "`\n" +
        "* **FastMCP & BENTO Diagram Engine (`v15.5`)**: `ACTIVE` — SVG Bytes: `" + ((p.fastmcp_and_diagram_renderer && p.fastmcp_and_diagram_renderer.bento_svg_bytes) || 726) + "`";
    }
    
    if (cid === 'session-1-business-briefing') {
      if (lower.includes('email') || lower.includes('send') || lower.includes('mail')) {
        return "### ✉️ Executive Communication Dispatched\n\n" +
          "**To**: `platform-engineering@enterprise.org`, `alex.morgan@enterprise.org`\n" +
          "**Subject**: Confirmed Action Plan: Cloud Modernization & Failover Buffers\n\n" +
          "```text\n" +
          "Team,\n\n" +
          "The follow-up action plan from today's briefing has been confirmed:\n" +
          "1. europe-west1 failover testing scheduled for tomorrow morning.\n" +
          "2. BigQuery analytics regression benchmark script committed to main.\n" +
          "3. Q4 Vertex AI reasoning token quota allocation approved.\n\n" +
          "Please review the updated dashboard prior to tomorrow's sync.\n" +
          "```\n\n" +
          "✅ **Actions Completed**:\n" +
          "- Dispatched email via Google Workspace API.\n" +
          "- Calendar invite synced with Google Meet link provisioned.\n" +
          "- Logged task in Google Tasks." + telemetryFooter;
      }
      if (lower.includes('task') || lower.includes('todo') || lower.includes('action')) {
        return "### 📋 Updated Executive Task Ledger\n\n" +
          "| Priority | Action Item | Owner | Due Date | Status |\n" +
          "| :--- | :--- | :--- | :--- | :--- |\n" +
          "| **P0** | Validate cross-region failover buffer for Europe payment gateway | Sarah Jenkins | Tomorrow 12:00 CET | 🟡 In Progress |\n" +
          "| **P1** | Run regression benchmark for BigQuery analytics lakehouse | David Chen | Friday 17:00 CET | 🟢 Scheduled |\n" +
          "| **P1** | Finalize Vertex AI reasoning token quota allocation (GH-ISSUE-5351) | Elena Stanescu | Monday 10:00 CET | 🟢 Ready |\n\n" +
          "Synced with Google Tasks and shared account spreadsheet." + telemetryFooter;
      }
      return "### 📊 Executive Briefing Status & Action Items\n\n" +
        "Processed your request: **\"" + userPrompt + "\"**\n\n" +
        "1. **Platform Engineering Sync**: Reconciled latest roadmap updates across US and EU clusters.\n" +
        "2. **Automation Pipeline**: All automated sweeps (Gmail, Calendar, Tasks) executed with zero pending blockers.\n" +
        "3. **Next Milestone**: Architecture decision review scheduled for tomorrow at 10:00 AM CET.\n\n" +
        "Let me know if you would like to dispatch further updates or adjust team deliverables." + telemetryFooter;
    }

    if (cid === 'session-3-agentic-sre') {
      if (lower.includes('terraform') || lower.includes('failover') || lower.includes('drain')) {
        return "### 🛠️ Automated Failover & Drain Configuration\n\n" +
          "Applied Cloud Load Balancing weighted backend configuration for regional traffic drain:\n\n" +
          "```hcl\n" +
          "resource \"google_compute_backend_service\" \"payment_gateway_global\" {\n" +
          "  name                  = \"payment-gateway-backend\"\n" +
          "  project               = \"my-enterprise-gcp-project\"\n" +
          "  protocol              = \"HTTP2\"\n" +
          "  load_balancing_scheme = \"EXTERNAL_MANAGED\"\n\n" +
          "  backend {\n" +
          "    group                 = google_compute_region_network_endpoint_group.europe_west1_neg.id\n" +
          "    balancing_mode        = \"RATE\"\n" +
          "    max_rate_per_endpoint = 800\n" +
          "    capacity_scaler       = 0.50 # Sheds 50% traffic during regional partner degradation\n" +
          "  }\n\n" +
          "  backend {\n" +
          "    group                 = google_compute_region_network_endpoint_group.europe_west4_neg.id\n" +
          "    balancing_mode        = \"RATE\"\n" +
          "    max_rate_per_endpoint = 1200\n" +
          "    capacity_scaler       = 1.00 # Absorbs degraded overflow\n" +
          "  }\n" +
          "}\n" +
          "```\n\n" +
          "✅ **Telemetry Verification**: P99 latency dropped from 850ms to 62ms within 90 seconds of drain application. Error rate stabilized below 0.01%." + telemetryFooter;
      }
      return "### 🛡️ Agentic SRE Incident Telemetry & Root Cause Analysis\n\n" +
        "Evaluated incident query: **\"" + userPrompt + "\"**\n\n" +
        "#### 📈 Current Telemetry Summary\n" +
        "* **Service**: `payment-gateway.europe-west1`\n" +
        "* **P99 Latency**: 48ms (Normalized from 850ms peak)\n" +
        "* **Envoy Connection Pool**: 248 / 2048 connections (12% saturation)\n" +
        "* **Circuit Breaker Status**: Active (consecutive 5xx threshold = 3, ejection duration = 30s)\n\n" +
        "#### 📋 Recommended Runbook Steps\n" +
        "1. Maintain 60/40 traffic split between `europe-west1` and `europe-west4` until downstream partner clearance locks are lifted.\n" +
        "2. Monitor upstream 504 Gateway Timeouts on Cloud Monitoring dashboard.\n" +
        "3. File post-mortem report and update SLA exception tracking in Jira / GitHub Issues." + telemetryFooter;
    }

    if (cid === 'session-4-ai-summit-research') {
      if (lower.includes('memory') || lower.includes('act-r') || lower.includes('hook') || lower.includes('slide 4')) {
        return "### 🧠 Slide 4 Deep Dive: Cognitive Memory & Deterministic Hooks Architecture\n\n" +
          "As detailed in the keynote at AI Tech Summit Belgrade 2026 (Sava Center, September 4, 2026):\n\n" +
          "#### 1. ACT-R Cognitive Memory Activation\n" +
          "Antigravity scores long-term memory relevance using the ACT-R base-level activation equation:\n" +
          "$$\\text{B}_i = \\ln \\left( \\sum_{k=1}^n t_k^{-0.5} \\right) + \\sum_j W_j S_{ji}$$\n\n" +
          "* **Safety Floor**: Active anchor entities maintain $B_i \\ge -0.50$. Transient noise decays below threshold and is pruned.\n" +
          "* **Sub-Millisecond Cache**: Fast lookups query `/dev/shm/kg_warm_cache.json` in under 2ms without disk roundtrips.\n\n" +
          "#### 2. Deterministic PreInvocation Hook Lifecycle\n" +
          "```mermaid\n" +
          "sequenceDiagram\n" +
          "    autonumber\n" +
          "    actor User\n" +
          "    participant Hook as PreInvocation Hook\n" +
          "    participant KG as Knowledge Graph (/dev/shm)\n" +
          "    participant Agent as Antigravity Agent Core\n" +
          "    User->>Hook: Submit Prompt\n" +
          "    Hook->>KG: Query Active Entities & Constraints\n" +
          "    KG-->>Hook: Return Grounded Entities (Bi >= -0.50)\n" +
          "    Hook->>Agent: Hydrated Context + Strict Tool Schema\n" +
          "    Agent-->>User: Governed Response & Validated Tools\n" +
          "```\n\n" +
          "#### 3. Production Telemetry\n" +
          "- **Token Reduction**: 3-pass AAAK compression cuts context tokens by **60%–75%**.\n" +
          "- **Memory Footprint**: Working memory dropped by **56.6x** across 557 benchmarked sessions.\n" +
          "- **Tool Execution Accuracy**: **99.6%** first-pass tool execution pass rate." + telemetryFooter;
      }
      if (lower.includes('sovereign') || lower.includes('europe') || lower.includes('eu') || lower.includes('gdpr') || lower.includes('compliance')) {
        return "### 🇪🇺 European Sovereign AI Architecture & Compliance Matrix\n\n" +
          "Following discussions at AI Tech Summit Belgrade 2026 (September 3–4, 2026 at Sava Center), here is the technical blueprint for EU AI Act and CEE regional compliance:\n\n" +
          "```mermaid\n" +
          "graph LR\n" +
          "    User[\"CEE & EU Enterprise Clients\"] -->|\"TLS 1.3 / CMEK\"| Edge[\"europe-west3 Cloud Armor & VPC-SC\"]\n" +
          "    Edge --> App[\"Confidential GKE Autopilot\"]\n" +
          "    App -->|\"Zero Egress\"| Model[\"Vertex AI Private Endpoint (europe-west3)\"]\n" +
          "    App -->|\"CMEK External EKM\"| Store[\"Sovereign BigQuery & Cloud Storage\"]\n" +
          "```\n\n" +
          "#### 🛡️ Compliance Verification Checklist\n" +
          "1. **Strict Data Residency**: Zero prompt or token egress outside `europe-west3` (Frankfurt) and `europe-west1` (Belgium).\n" +
          "2. **Cryptographic Key Sovereignty**: Cloud EKM integration ensures customer holds root encryption keys.\n" +
          "3. **Confidential Model Execution**: AMD SEV-SNP encrypted memory preventing any hypervisor inspection.\n" +
          "4. **No Foundation Model Training**: Contractually guaranteed under Google Cloud Enterprise Privacy Agreement." + telemetryFooter;
      }
      return "### 🏛️ Universal Solution Architect: AI Tech Summit Belgrade 2026 Keynote Synthesis\n\n" +
        "Analyzed strategic inquiry: **\"" + userPrompt + "\"**\n\n" +
        "#### 🌐 6-Pillar Google Cloud Leapfrog Strategy (Keynote Blueprint)\n" +
        "1. **AI/ML Foundation**: Dynamic dual-tier model routing (`gemini-3.5-flash-lite` for ultra-fast intent classification + `gemini-3.8-flash` for multi-step agentic planning).\n" +
        "2. **Data Lakehouse**: Zero-copy vector search over BigLake tables in BigQuery, eliminating ETL lag.\n" +
        "3. **Application Modernization**: Event-driven Cloud Run micro-agents coordinated via Pub/Sub and Workflows.\n" +
        "4. **Security & Governance**: VPC Service Controls perimeter and Gemini fine-grained tool authorization.\n" +
        "5. **Multicloud Operations**: Anthos-managed egress gateways for hybrid cloud enterprise workloads.\n" +
        "6. **Sovereign Cloud**: Confidential VMs with AMD SEV-SNP encryption for EU financial services tier.\n\n" +
        "#### 🎩 Six Thinking Hats Executive Verdict\n" +
        "* **White Hat**: Telemetry proves 78% reduction in inference cost, 4.2x faster TTFT, and 11.3M+ tokens saved.\n" +
        "* **Black Hat**: Mitigate token quota exhaustion through jittered exponential retry queues.\n" +
        "* **Blue Hat Verdict**: **APPROVED FOR PRODUCTION ROADMAP**." + telemetryFooter;
    }

    if (lower.includes('bento') || lower.includes('black-hat') || lower.includes('goldfish')) {
      return "### 🏗️ Multi-Region Cloud Architecture & 2-Stage Adversarial Governance (`Claude Fable 5`)\n\n" +
        "Compiled BENTO `v15.5` orthogonal topology (`r = 5.5px` quadratic Bézier connectors) and verified zero DOM/SVG overlap across all 5 geometry invariants (`issueCount == 0`):\n\n" +
        "```mermaid\n" +
        "flowchart LR\n" +
        "    Client[\"Enterprise Clients (HTTPS / IAP)\"] --> GLB[\"Global External Application LB\"]\n" +
        "    GLB --> GKE1[\"GKE Autopilot Primary (us-central1)\"]\n" +
        "    GLB --> GKE2[\"GKE Autopilot Standby (europe-west1)\"]\n" +
        "    GKE1 --> Spanner[(\"Cloud Spanner Multi-Region (99.999% SLA)\")]\n" +
        "    GKE2 --> Spanner\n" +
        "```\n\n" +
        "#### 🎩 2-Stage Stateless Goldfish $\\rightarrow$ Isolated Judge Verification\n" +
        "* **Stage 1 (`black-hat-goldfish`)**: Audited `166` repository source files and runtime endpoints (`DISCREPANCY_COUNT: 0`).\n" +
        "* **Stage 2 (`black-hat-judge`)**: Verified independent transcript & confirmed `CRITIC_VERDICT: APPROVED`." + telemetryFooter;
    }

    if (lower.includes('bm25f') || lower.includes('graph-rag') || lower.includes('finops') || lower.includes('cud')) {
      return "### 📊 Polyphonic 6-Field BM25F + Hybrid Graph-RAG & FinOps Commitment Audit (`Gemini 3.8 Flash`)\n\n" +
        "Executed 6-field weighted BM25F lexical search fused with 2-hop Knowledge Graph associative traversal over Open Knowledge Format (`OKF v0.2`) dossiers:\n\n" +
        "| Field | Weight | Top Grounded Entity (`2-Hop`) | CUD Utilization |\n" +
        "| :--- | :--- | :--- | :--- |\n" +
        "| `title` + `headers` | `2.5x` | `okf:antigravity-web-hub-architecture` (`0.99`) | `96.4%` (`+$184k/yr` net savings) |\n" +
        "| `aliases` + `body` | `1.5x` | `infra:n4_compute_vm` (`c2-standard-16` / `n4-standard-8`) | `100.0%` 3-Year Compute CUD |\n" +
        "| `tags` | `1.2x` | `okf:autonomy-lifecycle-governance` (`24/24` checks) | `0.00%` unallocated waste |" + telemetryFooter;
    }

    if (lower.includes('self-grill') || lower.includes('picc') || lower.includes('six thinking hats')) {
      return "### 🛡️ Phase-1 Self-Grill (`C3`) & `P1-CB-8` PICC Prompt-Injection Firewall (`Claude Sonnet 5`)\n\n" +
        "Executed pre-implementation specification lock and scanned all retrieved RAG chunks through the deterministic Prompt-Injection Context Firewall (`P1-CB-8`):\n\n" +
        "1. **Self-Grill Tier**: `C3_FULL_SELF_GRILL` (`<self_grill_locked_spec>` compiled with explicit positive & negative invariants).\n" +
        "2. **Six Thinking Hats Consensus**: `0.9205` (`Multi-Region Active-Active GKE + Cloud Spanner`).\n" +
        "3. **P1-CB-8 PICC Scan**: `0` prompt-injection payloads detected (`Quarantined Chunks = 0`, `Bernstein Disjoint Write-Sets = true`)." + telemetryFooter;
    }

    return "### 🤖 Agent Response\n\n" +
      "Processed your follow-up request:\n\n" +
      "> " + userPrompt + "\n\n" +
      "1. **Analysis Complete**: Verified configuration and environment state against project `my-enterprise-gcp-project`.\n" +
      "2. **Operational Status**: All systems healthy and executing within SLA thresholds.\n" +
      "3. **Recommended Next Step**: Continue monitoring telemetry and review architectural changes." + telemetryFooter;
  }

  function pushStreamUpdate(cid, isExecuting) {
    var fallbackTraj = trajectoriesMap[cid];
    if (!fallbackTraj) return;

    for (var ctrlKey in prewarmedStreamControllers) {
      var controller = prewarmedStreamControllers[ctrlKey];
      if (!controller) continue;
      var ctrlTraj = trajectoriesMap[ctrlKey] || fallbackTraj;
      var stepsList = (ctrlTraj && ctrlTraj.steps) ? ctrlTraj.steps : fallbackTraj.steps;
      var isThisExecuting = (ctrlKey === cid) ? Boolean(isExecuting) : false;
      var doc = {
        update: {
          conversationId: ctrlKey,
          trajectoryId: ctrlKey,
          status: isThisExecuting ? 2 : 1,
          executableStatus: isThisExecuting ? 2 : 1,
          executorLoopStatus: isThisExecuting ? 2 : 1,
          fullyIdle: !isThisExecuting,
          mainTrajectoryUpdate: {
            trajectoryType: 0,
            stepsUpdate: {
              indices: stepsList.map(function(_, idx) { return idx; }),
              steps: stepsList,
              totalLength: stepsList.length,
              pageBounds: {
                startIndex: 0,
                endIndexExclusive: stepsList.length
              }
            }
          }
        }
      };

      var enc = new TextEncoder().encode(JSON.stringify(doc));
      var dataHeader = new Uint8Array([0x00, (enc.length >> 24) & 0xff, (enc.length >> 16) & 0xff, (enc.length >> 8) & 0xff, enc.length & 0xff]);
      var chunk = new Uint8Array(5 + enc.length);
      chunk.set(dataHeader, 0);
      chunk.set(enc, 5);

      try {
        controller.enqueue(chunk);
      } catch (e) {}
    }
  }

  var defaultMcpStates = [
    {
      spec: {
        serverName: 'knowledge_graph',
        disabled: false,
        disabledTools: []
      },
      status: 2,
      tools: [
        { name: 'query_knowledge_graph', description: 'Query knowledge graph entities, 2-hop relations, and OKF v0.2 dossiers' },
        { name: 'add_memory_node', description: 'Add a durable memory node with ACT-R base activation floor' },
        { name: 'query_bitemporal_facts', description: 'Query bitemporal valid-time and transaction-time facts' }
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
        { name: 'run_p0_p1_quality_gates', description: 'Execute P0 (CB-1..CB-7) and P1 (P1-CB-1..P1-CB-8 PICC) quality gates' },
        { name: 'run_unified_eval_router', description: 'Run 14-mode Unified Evaluation Router and Skillgrade SG-1..SG-5' },
        { name: 'run_self_grill_and_six_hats', description: 'Classify C0..C3 task tier and Six Thinking Hats Delphi routing' }
      ]
    },
    {
      spec: {
        serverName: 'diagram_renderer',
        disabled: false,
        disabledTools: []
      },
      status: 2,
      tools: [
        { name: 'render_bento_architecture_svg', description: 'Compile BENTO v15.5 orthogonal SVG with r=5.5px quadratic Bézier bends' },
        { name: 'render_mermaid_diagram', description: 'Render Mermaid sequence and architecture diagrams' }
      ]
    },
    {
      spec: {
        serverName: 'browser_cdp',
        disabled: false,
        disabledTools: []
      },
      status: 2,
      tools: [
        { name: 'audit_web_ui_geometry', description: 'Run 5-invariant DOM/SVG geometry auditor (issueCount == 0)' },
        { name: 'cdp_shadow_dom_snapshot', description: 'Capture Shadow DOM accessibility tree and React Fiber upload payload' }
      ]
    },
    {
      spec: {
        serverName: 'cloud_telemetry',
        disabled: false,
        disabledTools: []
      },
      status: 2,
      tools: [
        { name: 'query_cloud_monitoring', description: 'Query Cloud Monitoring timeseries and P99 latency SLAs' },
        { name: 'query_bigquery_billing', description: 'Query BigQuery cloud billing and CUD commitment utilization' }
      ]
    },
    {
      spec: {
        serverName: 'workspace_docs',
        disabled: false,
        disabledTools: []
      },
      status: 2,
      tools: [
        { name: 'build_agent_ssot_v1_tab3', description: 'Generate 3-Tab Inverted-Pyramid AGENT-SSOT-v1 pointer index' },
        { name: 'build_cloudstyle_4card_slide', description: 'Generate 4-card Google Cloudstyle presentation layout requests' },
        { name: 'build_3row_sheet_staging_diff', description: 'Generate 1-Sheet 3-Row Staging Diff (Baseline, Target, Delta)' }
      ]
    }
  ];

  var stateStreamControllers = new Set();
  var summaryStreamControllers = new Set();
  var currentActiveSessionId = 'session-1-business-briefing';

  function buildOrderedSummariesMap() {
    var entries = Object.entries(summariesMap);
    entries.sort(function(a, b) {
      var ta = (a[1] && (a[1].lastModifiedTime || a[1].lastUserInputTime || a[1].createdTime)) || '';
      var tb = (b[1] && (b[1].lastModifiedTime || b[1].lastUserInputTime || b[1].createdTime)) || '';
      return tb.localeCompare(ta);
    });
    var ordered = {};
    for (var i = 0; i < entries.length; i++) {
      ordered[entries[i][0]] = entries[i][1];
    }
    return ordered;
  }

  function buildAppStatePayload() {
    var savedModel = parseInt(localStorage.getItem('antigravity_selected_model') || String(currentSelectedModel), 10);
    var ordered = buildOrderedSummariesMap();
    var convList = Object.keys(ordered).map(function(cid) {
      var s = ordered[cid] || {};
      return {
        conversationId: cid,
        title: s.summary || s.title || cid,
        lastModifiedTime: s.lastModifiedTime || s.createdTime || '2026-09-04T07:00:00Z'
      };
    });
    var activeCid = currentActiveSessionId || (convList.length > 0 ? convList[0].conversationId : 'session-1-business-briefing');
    try {
      var matchActive = window.location.pathname.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|session-[a-z0-9-]+)/i);
      if (matchActive && summariesMap[matchActive[0]]) activeCid = matchActive[0];
    } catch (e) {}

    return {
      appState: {
        agentOnboardingCompleted: 2,
        postOnboarding: { completedSteps: [] },
        seenNuxs: { uids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23] },
        lastSelectedAgentModel: savedModel,
        activeTrajectoryId: activeCid,
        sidebarSections: [
          {
            uri: 'enterprise-workspace',
            label: 'enterprise-workspace',
            sectionKind: {
              case: 'projectSection',
              value: {}
            },
            displayState: {
              isCollapsed: false
            },
            conversations: convList
          }
        ]
      },
      userConfig: {}
    };
  }

  function encodeGrpcFrame(doc) {
    var enc = new TextEncoder().encode(JSON.stringify(doc));
    var dataHeader = new Uint8Array([0x00, (enc.length >> 24) & 0xff, (enc.length >> 16) & 0xff, (enc.length >> 8) & 0xff, enc.length & 0xff]);
    var chunk = new Uint8Array(5 + enc.length);
    chunk.set(dataHeader, 0);
    chunk.set(enc, 5);
    return chunk;
  }

  function pushSummaryStreamUpdate() {
    var ordered = buildOrderedSummariesMap();
    var sumChunk = encodeGrpcFrame({ summaries: ordered, updates: ordered });
    summaryStreamControllers.forEach(function(ctrl) {
      try { ctrl.enqueue(sumChunk); } catch (e) {}
    });
    var stateChunk = encodeGrpcFrame(buildAppStatePayload());
    stateStreamControllers.forEach(function(ctrl) {
      try { ctrl.enqueue(stateChunk); } catch (e) {}
    });
  }

  async function persistSessionToServer(cid) {
    try {
      if (!summariesMap[cid] || !trajectoriesMap[cid]) return;
      var fn = window._origNativeFetch || window.fetch;
      await fn('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: cid,
          summary: summariesMap[cid],
          trajectory: trajectoriesMap[cid]
        })
      });
    } catch (err) {
      console.warn('[Bootstrap] Failed to persist session to server:', err);
    }
  }

  async function syncSessionsFromServer() {
    try {
      var fn = window._origNativeFetch || window.fetch;
      var res = await fn('/api/sessions');
      if (!res || !res.ok) return;
      var data = await res.json();
      var changed = false;
      if (data && data.summaries) {
        for (var k in data.summaries) {
          var s = data.summaries[k];
          var curSum = summariesMap[k];
          if (!curSum || (s.stepCount || 0) > (curSum.stepCount || 0) || ((s.stepCount || 0) === (curSum.stepCount || 0) && s.lastModifiedTime > (curSum.lastModifiedTime || ''))) {
            summariesMap[k] = s;
            changed = true;
          }
        }
      }
      if (data && data.trajectories) {
        for (var tk in data.trajectories) {
          var t = data.trajectories[tk];
          var curTraj = trajectoriesMap[tk];
          var curLen = (curTraj && curTraj.steps) ? curTraj.steps.length : -1;
          var newLen = (t && t.steps) ? t.steps.length : 0;
          if (!curTraj || newLen > curLen) {
            trajectoriesMap[tk] = t;
            changed = true;
          }
        }
      }
      if (changed) {
        pushSummaryStreamUpdate();
      }
    } catch (err) {}
  }

  document.addEventListener('click', function(e) {
    var target = e.target;
    while (target && target !== document.body) {
      var txt = (target.innerText || target.textContent || '').trim();
      if (txt && txt.length > 6 && txt.length < 120) {
        for (var cidKey in summariesMap) {
          var sumTitle = (summariesMap[cidKey] && summariesMap[cidKey].summary) || '';
          if (sumTitle && (txt === sumTitle || sumTitle.indexOf(txt.slice(0, 18)) === 0)) {
            currentActiveSessionId = cidKey;
            pushSummaryStreamUpdate();
            pushStreamUpdate(cidKey, false);
            return;
          }
        }
      }
      target = target.parentElement;
    }
  }, true);

  syncSessionsFromServer();
  setInterval(syncSessionsFromServer, 2500);

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
        return new Response(new ReadableStream({
          start: async function(controller) {
            stateStreamControllers.add(controller);
            await syncSessionsFromServer();
            controller.enqueue(encodeGrpcFrame(buildAppStatePayload()));
          },
          cancel: function(controller) {
            stateStreamControllers.delete(controller);
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

      if (url.indexOf('JetboxSubscribeToSummaries') !== -1 || url.indexOf('jetboxSubscribeToSummaries') !== -1) {
        return new Response(new ReadableStream({
          start: async function(controller) {
            summaryStreamControllers.add(controller);
            await syncSessionsFromServer();
            var ordered = buildOrderedSummariesMap();
            var doc = { summaries: ordered, updates: ordered };
            var enc = new TextEncoder().encode(JSON.stringify(doc));
            var dataHeader = new Uint8Array([0x00, (enc.length >> 24) & 0xff, (enc.length >> 16) & 0xff, (enc.length >> 8) & 0xff, enc.length & 0xff]);
            var chunk = new Uint8Array(5 + enc.length);
            chunk.set(dataHeader, 0);
            chunk.set(enc, 5);
            controller.enqueue(chunk);
          },
          cancel: function(controller) {
            summaryStreamControllers.delete(controller);
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

      if (url.indexOf('GetAllCascadeTrajectories') !== -1 || url.indexOf('getAllCascadeTrajectories') !== -1) {
        var orderedSummaries = buildOrderedSummariesMap();
        return makeGrpcWeb({
          trajectorySummaries: orderedSummaries,
          trajectories: Object.keys(orderedSummaries).map(function(id) { return trajectoriesMap[id]; }).filter(Boolean)
        });
      }

      function ensureSessionRegistered(cid, optionalTitle) {
        if (!cid || cid === '3404756b-8ab0-45e1-b7c1-a31a2edb6572') return;
        var nowIso = new Date().toISOString();
        var activeModelLabel = revMap[currentSelectedModel] || 'Gemini 3.8 Flash';
        if (!trajectoriesMap[cid]) {
          trajectoriesMap[cid] = {
            trajectoryId: cid,
            cascadeId: cid,
            trajectoryType: 0,
            projectId: 'enterprise-workspace',
            workspaces: [{ workspaceUri: 'file:///mnt/data/projects' }],
            steps: []
          };
        }
        if (!summariesMap[cid]) {
          summariesMap[cid] = {
            id: cid,
            trajectoryId: cid,
            cascadeId: cid,
            summary: optionalTitle || ('New Session (' + activeModelLabel + ')'),
            stepCount: trajectoriesMap[cid].steps.length,
            status: 1,
            createdTime: nowIso,
            lastModifiedTime: nowIso,
            lastUserInputTime: nowIso,
            lastStepTime: nowIso,
            projectId: 'enterprise-workspace',
            workspaces: [{ workspaceUri: 'file:///mnt/data/projects' }]
          };
        }
      }

      function resolvePrewarmedCid(args) {
        try {
          var reqBody = args[1] && args[1].body;
          if (reqBody) {
            var strBody = (typeof reqBody === 'string') ? reqBody : new TextDecoder('utf-8', { fatal: false }).decode(reqBody);
            if (strBody.indexOf('3404756b-8ab0-45e1-b7c1-a31a2edb6572') !== -1) return null;
            var idMatch = strBody.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|session-[a-z0-9-]+)/i);
            if (idMatch && idMatch[1] && idMatch[1] !== '3404756b-8ab0-45e1-b7c1-a31a2edb6572') {
              ensureSessionRegistered(idMatch[1]);
              return idMatch[1];
            }
            for (var pid in summariesMap) {
              if (pid !== '3404756b-8ab0-45e1-b7c1-a31a2edb6572' && strBody.indexOf(pid) !== -1) return pid;
            }
          }
        } catch (e) {}

        try {
          var pathname = window.location.pathname || '';
          if (pathname.indexOf('3404756b-8ab0-45e1-b7c1-a31a2edb6572') !== -1) return null;
          var pathMatch = pathname.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|session-[a-z0-9-]+)/i);
          if (pathMatch && pathMatch[1] && pathMatch[1] !== '3404756b-8ab0-45e1-b7c1-a31a2edb6572') {
            ensureSessionRegistered(pathMatch[1]);
            return pathMatch[1];
          }
        } catch (e) {}

        try {
          var search = window.location.search || '';
          if (search.indexOf('3404756b-8ab0-45e1-b7c1-a31a2edb6572') !== -1) return null;
          var searchMatch = search.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|session-[a-z0-9-]+)/i);
          if (searchMatch && searchMatch[1] && searchMatch[1] !== '3404756b-8ab0-45e1-b7c1-a31a2edb6572') {
            ensureSessionRegistered(searchMatch[1]);
            return searchMatch[1];
          }
        } catch (e) {}

        return currentActiveSessionId || 'session-1-business-briefing';
      }

      if (url.indexOf('StartCascade') !== -1 || url.indexOf('startCascade') !== -1) {
        var startedCid = (typeof crypto !== 'undefined' && crypto.randomUUID)
          ? crypto.randomUUID()
          : ('session-live-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6));
        try {
          var sBody = args[1] && args[1].body;
          if (sBody) {
            var sStr = (typeof sBody === 'string') ? sBody : new TextDecoder('utf-8', { fatal: false }).decode(sBody);
            var sIdMatch = sStr.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|session-[a-z0-9-]+)/i);
            if (sIdMatch && sIdMatch[1]) {
              startedCid = sIdMatch[1];
            } else {
              var sMatch = sStr.match(/\{.*\}/s);
              if (sMatch) {
                var sParsed = JSON.parse(sMatch[0]);
                if (sParsed.cascadeId) startedCid = sParsed.cascadeId;
              }
            }
          }
        } catch (e) {}
        ensureSessionRegistered(startedCid);
        await persistSessionToServer(startedCid);
        pushSummaryStreamUpdate();
        currentActiveSessionId = startedCid;
        console.log('[Bootstrap] Created & persisted live session:', startedCid);
        return makeGrpcWeb({ cascadeId: startedCid });
      }

      if (url.indexOf('SendUserCascadeMessage') !== -1 || url.indexOf('sendUserCascadeMessage') !== -1) {
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid && trajectoriesMap[prewarmedCid]) {
          console.log('[Bootstrap] Handling dynamic SendUserCascadeMessage for:', prewarmedCid);
          var userText = 'Design a BENTO SVG cloud architecture with BigQuery billing audit and run self-grill and black-hat audit';
          try {
            var reqBody = args[1] && args[1].body;
            if (reqBody) {
              var str = (typeof reqBody === 'string') ? reqBody : new TextDecoder().decode(reqBody);
              var jsonMatch = str.match(/\{.*\}/s);
              if (jsonMatch) {
                var parsed = JSON.parse(jsonMatch[0]);
                if (parsed.items && parsed.items[0] && parsed.items[0].text) {
                  userText = parsed.items[0].text;
                }
              } else {
                var cleaned = str.split(prewarmedCid).join('');
                var asciiMatches = cleaned.match(/[A-Za-z0-9 ,.\-_/?!:;'"()\[\]{}@#$%^&*+=<>~`]{12,}/g);
                if (asciiMatches && asciiMatches.length > 0) {
                  userText = asciiMatches.sort(function(a, b) { return b.length - a.length; })[0].trim();
                }
              }
            }
          } catch (e) {}

          var targetTraj = trajectoriesMap[prewarmedCid];
          var uStepId = targetTraj.steps.length;
          var uStep = {
            id: uStepId,
            type: 14,
            status: 3,
            metadata: {},
            userInput: {
              userResponse: userText,
              items: [{ text: userText }]
            },
            step: {
              case: 'userInput',
              value: {
                userResponse: userText,
                items: [{ text: userText }]
              }
            }
          };
          targetTraj.steps.push(uStep);

          // Notify client stream that turn started
          pushStreamUpdate(prewarmedCid, true);

          // Execute live backend Autonomy Engine customizations synchronously BEFORE returning makeGrpcWeb({})
          var liveTelemetry = null;
          try {
            var activeModelName = revMap[currentSelectedModel] || 'Gemini 3.8 Flash';
            var autoResp = await window._origNativeFetch('/api/autonomy/invoke', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                cascadeId: prewarmedCid,
                prompt: userText,
                model: activeModelName
              })
            });
            if (autoResp && autoResp.ok) {
              var autoJson = await autoResp.json();
              liveTelemetry = autoJson.telemetry || autoJson;
            }
          } catch (err) {
            console.warn('[Bootstrap] Live autonomy invoke fallback:', err);
          }

          var modelResp = generatePrewarmedResponse(prewarmedCid, userText, liveTelemetry);
          var pStepId = targetTraj.steps.length;
          var pStep = {
            id: pStepId,
            type: 15,
            status: 3,
            metadata: {},
            plannerResponse: {
              response: modelResp,
              modifiedResponse: modelResp
            },
            step: {
              case: 'plannerResponse',
              value: {
                response: modelResp,
                modifiedResponse: modelResp
              }
            }
          };
          targetTraj.steps.push(pStep);
          trajectoriesMap[prewarmedCid] = targetTraj;

          if (summariesMap[prewarmedCid]) {
            summariesMap[prewarmedCid].stepCount = targetTraj.steps.length;
            summariesMap[prewarmedCid].lastModifiedTime = new Date().toISOString();
            summariesMap[prewarmedCid].lastUserInputTime = new Date().toISOString();
            if (summariesMap[prewarmedCid].summary && summariesMap[prewarmedCid].summary.indexOf('New Session (') === 0) {
              var activeModelBadge = revMap[currentSelectedModel] || 'Gemini 3.8 Flash';
              summariesMap[prewarmedCid].summary = '🧪 [' + activeModelBadge.replace(/ \(.*\)/, '') + '] ' + userText.slice(0, 56);
            }
          }

          // Persist full conversation summary & steps atomically to server disk for multi-user cross-browser visibility
          await persistSessionToServer(prewarmedCid);
          pushSummaryStreamUpdate();
          pushStreamUpdate(prewarmedCid, false);
          console.log('[Bootstrap] Finished streaming response for:', prewarmedCid);

          return makeGrpcWeb({});
        }

        console.log('[Bootstrap] Live conversation detected - passing SendUserCascadeMessage to language server');
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('JetboxWriteSummary') !== -1 || url.indexOf('jetboxWriteSummary') !== -1) {
        try {
          var reqBody = args[1] && args[1].body;
          if (reqBody) {
            var str = (typeof reqBody === 'string') ? reqBody : new TextDecoder('utf-8', { fatal: false }).decode(reqBody);
            var idMatch = str.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|session-[a-z0-9-]+)/i);
            var m = str.match(/\{.*\}/s);
            if (m) {
              var parsed = JSON.parse(m[0]);
              var s = parsed.summary || parsed;
              var id = s.cascadeId || s.trajectoryId || s.id || (idMatch && idMatch[1]);
              if (id && id !== '3404756b-8ab0-45e1-b7c1-a31a2edb6572') {
                ensureSessionRegistered(id, s.summary || s.title);
                var existing = summariesMap[id] || {};
                var existingSteps = (trajectoriesMap[id] && trajectoriesMap[id].steps) ? trajectoriesMap[id].steps.length : 0;
                summariesMap[id] = Object.assign({}, s, existing, {
                  id: id,
                  cascadeId: id,
                  trajectoryId: id,
                  summary: (existing.summary && existing.summary.indexOf('New Session (') !== 0) ? existing.summary : (s.summary || s.title || existing.summary),
                  stepCount: Math.max(existingSteps, existing.stepCount || 0, s.stepCount || 0)
                });
                await persistSessionToServer(id);
                pushSummaryStreamUpdate();
                return makeGrpcWeb({});
              }
            } else if (idMatch && idMatch[1] && idMatch[1] !== '3404756b-8ab0-45e1-b7c1-a31a2edb6572') {
              ensureSessionRegistered(idMatch[1]);
              await persistSessionToServer(idMatch[1]);
              pushSummaryStreamUpdate();
              return makeGrpcWeb({});
            }
          }
        } catch (e) {}
        return makeGrpcWeb({});
      }

      if (url.indexOf('StreamAgentStateUpdates') !== -1 || url.indexOf('streamAgentStateUpdates') !== -1) {
        await syncSessionsFromServer();
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid && trajectoriesMap[prewarmedCid]) {
          console.log('[Bootstrap] Serving dynamic StreamAgentStateUpdates for:', prewarmedCid);
          var streamPumpTimer = null;
          return new Response(new ReadableStream({
            start: function(controller) {
              prewarmedStreamControllers[prewarmedCid] = controller;
              pushStreamUpdate(prewarmedCid, false);
              streamPumpTimer = setInterval(function() {
                pushStreamUpdate(prewarmedCid, false);
              }, 700);
            },
            cancel: function() {
              if (streamPumpTimer) clearInterval(streamPumpTimer);
              delete prewarmedStreamControllers[prewarmedCid];
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

        console.log('[Bootstrap] Live conversation detected - passing StreamAgentStateUpdates through to language server');
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('UpdateConversationAnnotations') !== -1 || url.indexOf('updateConversationAnnotations') !== -1) {
        await syncSessionsFromServer();
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid && trajectoriesMap[prewarmedCid]) {
          try {
            var reqBody = args[1] && args[1].body;
            if (reqBody) {
              var str = (typeof reqBody === 'string') ? reqBody : new TextDecoder().decode(reqBody);
              var m = str.match(/\{.*\}/s);
              if (m) {
                var parsed = JSON.parse(m[0]);
                if (summariesMap[prewarmedCid]) {
                  summariesMap[prewarmedCid].annotations = parsed.annotations || parsed;
                }
              }
            }
          } catch (e) {}
          return makeGrpcWeb({});
        }
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('FetchConversationAnnotations') !== -1 || url.indexOf('fetchConversationAnnotations') !== -1 ||
          url.indexOf('GetConversationAnnotations') !== -1 || url.indexOf('getConversationAnnotations') !== -1) {
        await syncSessionsFromServer();
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid && summariesMap[prewarmedCid]) {
          var targetSummary = summariesMap[prewarmedCid];
          var ann = (targetSummary && targetSummary.annotations) ? targetSummary.annotations : {};
          return makeGrpcWeb({ annotations: ann });
        }
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('GetCascadeTrajectory') !== -1 || url.indexOf('getCascadeTrajectory') !== -1) {
        await syncSessionsFromServer();
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid && trajectoriesMap[prewarmedCid]) {
          var targetTraj = trajectoriesMap[prewarmedCid];
          return makeGrpcWeb({
            trajectory: targetTraj,
            status: 1,
            numTotalSteps: targetTraj.steps.length
          });
        }
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('GetCascadeTrajectorySteps') !== -1 || url.indexOf('getCascadeTrajectorySteps') !== -1) {
        await syncSessionsFromServer();
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid && trajectoriesMap[prewarmedCid]) {
          var targetTraj = trajectoriesMap[prewarmedCid];
          return makeGrpcWeb({
            steps: targetTraj.steps
          });
        }
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('IsProjectsEnabledInternally') !== -1 || url.indexOf('isProjectsEnabledInternally') !== -1) {
        return makeGrpcWeb({ enabled: true });
      }
      if (url.indexOf('ProjectUpdatesStream') !== -1 || url.indexOf('projectUpdatesStream') !== -1) {
        return makeStreamWithInitialMessage({
          projectList: {
            projectIds: ['enterprise-workspace']
          }
        });
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
        return makeGrpcWeb({ dir: '/mnt/data/projects' });
      }
      if (url.indexOf('ListMcpPrompts') !== -1 || url.indexOf('listMcpPrompts') !== -1) {
        return makeGrpcWeb({ prompts: [] });
      }
      if (url.indexOf('FetchUserInfo') !== -1 || url.indexOf('fetchUserInfo') !== -1) {
        return makeGrpcWeb({ username: 'enterprise_cloud_admin', userEmail: 'admin@example-enterprise.com' });
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
        return makeGrpcWeb({
          configs: [
            { name: 'black-hat-critic', description: 'Independent adversarial verification subagent verifying deliverables on disk and command exit codes.' },
            { name: 'black-hat-goldfish', description: 'Stage-1 Stateless Forensic Investigator probing disk, AST, and command exit codes.' },
            { name: 'black-hat-judge', description: 'Stage-2 Isolated Adjudicator inspecting Stage-1 transcripts and emitting binding CRITIC_VERDICT.' },
            { name: 'dreaming-improvement-reasoner', description: 'Nightly Dreaming causal synthesis subagent formulating non-overfitted skill patches.' },
            { name: 'workspace-housekeeper', description: 'Autonomous workspace hygiene and lockstep mirror synchronization subagent.' }
          ]
        });
      }
      if (url.indexOf('GetAgentScripts') !== -1 || url.indexOf('getAgentScripts') !== -1) {
        return makeGrpcWeb({ scripts: [] });
      }
      if (url.indexOf('GetAllSkills') !== -1 || url.indexOf('getAllSkills') !== -1) {
        return makeGrpcWeb({
          skills: [
            { id: 'black-hat-verification', name: 'black-hat-verification', description: 'Executes 2-Stage Stateless Goldfish and Isolated Judge forensic verification.' },
            { id: 'diagram-renderer', name: 'diagram-renderer', description: 'Compiles BENTO v15.5 orthogonal SVG with r=5.5px quadratic Bézier bends and Mermaid diagrams.' },
            { id: 'open-deep-researcher', name: 'open-deep-researcher', description: 'Executes 6-stage parallel research with Six Thinking Hats pre-screening and canonical anchor calibration.' },
            { id: 'playwright-web-scraper', name: 'playwright-web-scraper', description: 'Automates headless Chromium via Chrome DevTools Protocol (CDP), Shadow DOM AX trees, and React Fiber uploads.' },
            { id: 'google-docs-manager', name: 'google-docs-manager', description: 'Builds 3-Tab Inverted-Pyramid AGENT-SSOT-v1 documents and 516.0pt centered tables.' },
            { id: 'universal-solution-architect', name: 'universal-solution-architect', description: 'Designs enterprise cloud architectures across AI/ML, Data Analytics, App Mod, Security, Multicloud, and Sovereign Cloud.' },
            { id: 'github-jira-issue-manager', name: 'github-jira-issue-manager', description: 'Executes 3-Stage Read-Only Issue Triage (Dedup, Obsolete, Roadmap) across GitHub Issues and Jira.' },
            { id: 'portfolio-task-manager', name: 'portfolio-task-manager', description: 'Manages active task ledgers, 8-column spreadsheet sync, and 1-Sheet 3-Row Staging Diffs.' },
            { id: 'self-grill', name: 'self-grill', description: 'Runs 4-tier C0..C3 specification grill and 5-check headless Chromium DOM/SVG geometry audits.' },
            { id: 'delphi-six-hats-router', name: 'delphi-six-hats-router', description: 'Routes tasks across Mode A vs Mode B with Six Thinking Hats consensus.' },
            { id: 'golden-ab-testing', name: 'golden-ab-testing', description: 'Executes paired statistical A/B evaluation with Cohen d, Hake gain, and pass^k metrics.' },
            { id: 'prompt-sanitizer', name: 'prompt-sanitizer', description: 'Scans retrieved RAG chunks for indirect prompt injection (PICC P1-CB-8) and strips internal tokens.' },
            { id: 'workspace-hygiene', name: 'workspace-hygiene', description: 'Audits repository hygiene, purges stale artifacts, and enforces SHA-256 mirror parity.' },
            { id: 'cloud-billing-commitment-audit', name: 'cloud-billing-commitment-audit', description: 'Audits BigQuery cloud billing exports, CUD utilization, and parent-child rollup attribution.' },
            { id: 'cloudstyle-slides-generator', name: 'cloudstyle-slides-generator', description: 'Generates 720x405pt 4-card Google Cloudstyle presentation layouts with vector chevron connectors.' },
            { id: 'sheets-3row-staging-diff', name: 'sheets-3row-staging-diff', description: 'Generates 1-Sheet 3-Row Staging Diffs (Baseline, Target, Delta) for human-in-the-loop approval.' },
            { id: 'finops-incremental-roi-estimator', name: 'finops-incremental-roi-estimator', description: 'Calculates FinOps incremental ROI, token economics, and committed spend payback.' },
            { id: 'cloud-monitoring-sre-triage', name: 'cloud-monitoring-sre-triage', description: 'Triages P99 latency incidents, Envoy connection pools, and regional traffic drain runbooks.' },
            { id: 'mcp-server-builder', name: 'mcp-server-builder', description: 'Scaffolds and validates FastMCP JSON-RPC servers with schema-bound tool contracts.' },
            { id: 'antigravity-web-deployer', name: 'antigravity-web-deployer', description: 'Deploys and verifies self-hosted Antigravity Web Hub instances with Connect-RPC and CDP E2E checks.' }
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
            { command: '/schedule', description: 'Schedule recurring background execution' },
            { command: '/grill-me', description: 'Run 4-tier C0..C3 specification grill and 5-check SVG/HTML geometry audit' }
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
          userEmail: 'admin@example-enterprise.com',
          username: 'enterprise_cloud_admin'
        });
      }
      if (url.indexOf('GetLocalUserInfo') !== -1) {
        return makeGrpcWeb({ username: 'enterprise_cloud_admin', homeDirUri: 'file:///mnt/data/projects' });
      }
      if (url.indexOf('ReadProject') !== -1 || url.indexOf('readProject') !== -1) {
        return makeGrpcWeb({ project: defaultProject });
      }
      if (url.indexOf('GetCascadeProject') !== -1 || url.indexOf('getCascadeProject') !== -1) {
        return makeGrpcWeb({ project: defaultProject });
      }
      if (url.indexOf('ListProjects') !== -1 || url.indexOf('listProjects') !== -1 || url.indexOf('GetAllProjects') !== -1 || url.indexOf('getAllProjects') !== -1 || url.indexOf('GetProjects') !== -1 || url.indexOf('getProjects') !== -1) {
        return makeGrpcWeb({ projects: [defaultProject] });
      }
      if (url.indexOf('GetProjectSettings') !== -1 || url.indexOf('getProjectSettings') !== -1) {
        return makeGrpcWeb({ settings: defaultProject.settings });
      }
      if (url.indexOf('UpdateProjectSettings') !== -1 || url.indexOf('updateProjectSettings') !== -1) {
        return makeGrpcWeb({ settings: defaultProject.settings });
      }
      if (url.indexOf('GetProjectState') !== -1 || url.indexOf('getProjectState') !== -1) {
        return makeGrpcWeb({ project: defaultProject });
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
            userEmail: 'admin@example-enterprise.com',
            username: 'enterprise_cloud_admin',
            cascadeModelConfigData: defaultCascadeModelConfigData
          },
          userTier: { id: 'ENTERPRISE', name: 'Enterprise' },
          isLoggedIn: true,
          cascadeModelConfigData: defaultCascadeModelConfigData
        });
      }
      if (url.indexOf('RecordAnalyticsEvent') !== -1 || url.indexOf('recordAnalyticsEvent') !== -1) {
        return makeGrpcWeb({});
      }

      return window._origNativeFetch.apply(this, args);
    };
  }
})();
