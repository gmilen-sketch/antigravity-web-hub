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
    localStorage.setItem('projectsGroupBy', 'project');
    localStorage.setItem('projectsGroupByInternal', 'project');
    localStorage.setItem('selectedProjectId', 'second-test-project');
    localStorage.setItem('currentSection', 'second-test-project');
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
    'selectedWorkspaceUri': 'file:///home/admin_mgenchev_altostrat_com/second-test-project',
    'selectedProjectId': 'second-test-project',
    'openProjects': JSON.stringify(['second-test-project', 'file:///home/admin_mgenchev_altostrat_com/second-test-project']),
    'recentProjects': JSON.stringify(['second-test-project', 'file:///home/admin_mgenchev_altostrat_com/second-test-project']),
    'lastOpenedWorkspace': 'file:///home/admin_mgenchev_altostrat_com/second-test-project',
    'currentSection': 'second-test-project',
    'projectsGroupBy': 'project',
    'projectsGroupByInternal': 'project'
  };

  var listeners = new Set();
  var currentSelectedModel = parseInt(localStorage.getItem('antigravity_selected_model') || '354', 10);

  var revMap = {
    354: 'Gemini 3.8 Flash',
    352: 'Gemini 3.7 Flash',
    350: 'Gemini 3.6 Flash',
    330: 'Gemini 3.5 Flash Lite',
    246: 'Gemini 3.5 Pro'
  };

  var modelMap = {
    'Gemini 3.8 Flash': { name: 'Gemini 3.8 Flash', enumVal: 354 },
    'Gemini 3.7 Flash': { name: 'Gemini 3.7 Flash', enumVal: 352 },
    'Gemini 3.6 Flash': { name: 'Gemini 3.6 Flash', enumVal: 350 },
    'Gemini 3.5 Flash Lite': { name: 'Gemini 3.5 Flash Lite', enumVal: 330 },
    'Gemini 3.5 Pro': { name: 'Gemini 3.5 Pro', enumVal: 246 }
  };

  function updateModelButtonText(modelName) {
    var btns = Array.from(document.querySelectorAll('button'));
    var mainBtn = btns.find(function(b) {
      var t = b.innerText || '';
      return t.indexOf('Gemini') !== -1 && t.indexOf('\n') === -1;
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
      target = target.parentElement;
    }
  }, true);

  setInterval(function() {
    var saved = parseInt(localStorage.getItem('antigravity_selected_model') || '354', 10);
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
    id: 'second-test-project',
    projectId: 'second-test-project',
    name: 'second-test-project',
    rootUri: 'file:///home/admin_mgenchev_altostrat_com/second-test-project',
    projectResources: {
      resources: [
        {
          resource: {
            uri: 'file:///home/admin_mgenchev_altostrat_com/second-test-project'
          }
        }
      ]
    },
    environments: {
      environments: [
        {
          id: 'second-test-project-env',
          name: 'second-test-project',
          resources: {
            resources: [
              {
                resource: {
                  uri: 'file:///home/admin_mgenchev_altostrat_com/second-test-project'
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
        label: 'Gemini 3.8 Flash',
        modelOrAlias: { choice: { case: 'model', value: 354 } },
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
        modelOrAlias: { choice: { case: 'model', value: 352 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Thinking & Reasoning',
        tagDescription: 'Dynamic thought circulation and advanced coding',
        supportsThoughtCirculation: true
      },
      {
        label: 'Gemini 3.6 Flash',
        modelOrAlias: { choice: { case: 'model', value: 350 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'General Production',
        tagDescription: 'Multimodal workflows and agentic swarms',
        supportsThoughtCirculation: true
      },
      {
        label: 'Gemini 3.5 Flash Lite',
        modelOrAlias: { choice: { case: 'model', value: 330 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'High-Throughput',
        tagDescription: 'Ultra-fast extraction and deterministic routing',
        supportsThoughtCirculation: true
      },
      {
        label: 'Gemini 3.5 Pro',
        modelOrAlias: { choice: { case: 'model', value: 246 } },
        disabled: false,
        supportedMimeTypes: {},
        quotaInfo: { remaining: 1000, total: 1000 },
        tagTitle: 'Extended Context',
        tagDescription: 'Deep synthesis and extended context (>1M)',
        supportsThoughtCirculation: true
      }
    ],
    clientModelSorts: [
      {
        name: 'Recommended',
        groups: [
          {
            groupName: 'Gemini Family',
            modelLabels: [
              'Gemini 3.8 Flash',
              'Gemini 3.7 Flash',
              'Gemini 3.6 Flash',
              'Gemini 3.5 Flash Lite',
              'Gemini 3.5 Pro'
            ]
          }
        ]
      },
      {
        name: 'All',
        groups: [
          {
            groupName: 'All Gemini Models',
            modelLabels: [
              'Gemini 3.8 Flash',
              'Gemini 3.7 Flash',
              'Gemini 3.6 Flash',
              'Gemini 3.5 Flash Lite',
              'Gemini 3.5 Pro'
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
      "projectId": "second-test-project"
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
      "projectId": "second-test-project"
    },
    "turns": [
      {
        "user": "Query our synthetic_analytics.cloud_billing_summary and support_cases datasets in BigQuery for project second-test-project-393510. Find our monthly cloud spend breakdown by service and SKU, correlate with high-priority support cases, and recommend immediate cost optimization actions.",
        "model": "### \ud83d\udcca BigQuery Enterprise Cloud Spend & Support Correlation Analysis\n\nExecuted query against `second-test-project-393510.synthetic_analytics.cloud_billing_summary` and `support_cases`:\n\n```sql\nSELECT \n  b.service_description,\n  b.sku_description,\n  ROUND(SUM(b.unblended_cost), 2) AS gross_spend_usd,\n  ROUND(SUM(b.credits_amount), 2) AS credits_usd,\n  ROUND(SUM(b.net_cost), 2) AS net_spend_usd,\n  COUNT(DISTINCT s.case_id) AS linked_support_cases\nFROM `second-test-project-393510.synthetic_analytics.cloud_billing_summary` b\nLEFT JOIN `second-test-project-393510.synthetic_analytics.support_cases` s\n  ON b.service_description = s.service\nGROUP BY 1, 2\nORDER BY net_spend_usd DESC\nLIMIT 5;\n```\n\n#### \ud83d\udcc8 Spend & Operational Health Matrix\n| Service Description | Primary SKU Description | Gross Spend | Credits / CUD | Net Effective Spend | Open Cases | Health Status |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| **Compute Engine** | N2 Core Instance running in europe-west1 | $14,850.20 | -$3,210.00 | **$11,640.20** | 1 | \ud83d\udfe2 Stable |\n| **BigQuery** | Analysis per Byte Scanned (Enterprise) | $8,940.00 | -$1,450.00 | **$7,490.00** | 0 | \ud83d\udfe2 Optimized |\n| **Cloud Storage** | Standard Storage Multi-Region EU | $3,420.50 | -$480.00 | **$2,940.50** | 0 | \ud83d\udfe2 Stable |\n| **Vertex AI** | Generative AI Prediction (Gemini 3.8 Flash) | $2,810.00 | -$310.00 | **$2,500.00** | 2 | \ud83d\udfe1 Monitor |\n| **Cloud Load Balancing** | Global L7 Forwarding Rule & Data Processing | $1,280.00 | -$150.00 | **$1,130.00** | 0 | \ud83d\udfe2 Optimal |\n\n#### \ud83d\udca1 Immediate Optimization Recommendations\n1. **Compute Engine Committed Use Discounts (CUD)**: 28% of baseline N2 instances currently run on uncommitted on-demand pricing. Committing to a 1-year CUD will save **$3,250/month**.\n2. **BigLake & Partition Pruning**: Enforcing mandatory partition filters on analytics queries reduces monthly BigQuery scan costs by **~42%**.\n\n> \u26a1 **Live Inference Active**: This session is wired directly to the live BigQuery instance in `second-test-project-393510`. Submit any follow-up question in the prompt box below to run live inference and queries against BigQuery!"
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
      "projectId": "second-test-project"
    },
    "turns": [
      {
        "user": "Investigate a high-priority incident: P99 latency spiked from 45ms to 850ms on the payment-gateway service in europe-west1. Outline root cause analysis steps, mitigation runbook, and circuit breaker configuration.",
        "model": "### \ud83d\udea8 Incident RCA: Payment Gateway P99 Latency Degradation\n\n* **Incident Summary**: At 14:12 UTC, P99 latency on `payment-gateway.europe-west1` increased from 45ms to 850ms, generating 504 Gateway Timeouts on upstream checkout flows.\n* **Root Cause**: Downstream banking clearance partner introduced a 500ms synchronous lock on debit transactions, causing connection pool exhaustion on our Envoy ingress proxy (all 2,048 worker threads saturated).\n\n### \ud83d\udee1\ufe0f Immediate Mitigation Runbook\n1. **Divert Traffic**: Shift 40% of non-essential checkout traffic to `europe-west4` gateway via Cloud Load Balancing weighted routing.\n2. **Apply Circuit Breaker**: Throttle calls to clearance endpoint when consecutive 5xx errors exceed 5% over 10 seconds.\n\n```yaml\napiVersion: networking.istio.io/v1alpha3\nkind: DestinationRule\nmetadata:\n  name: payment-gateway-circuit-breaker\n  namespace: payments-prod\nspec:\n  host: payment-gateway.service.internal\n  trafficPolicy:\n    connectionPool:\n      tcp:\n        maxConnections: 1024\n      http:\n        http1MaxPendingRequests: 100\n        maxRequestsPerConnection: 10\n    outlierDetection:\n      consecutive5xxErrors: 3\n      interval: 10s\n      baseEjectionTime: 30s\n      maxEjectionPercent: 50\n```"
      },
      {
        "user": "Generate the automated failover Terraform configuration to divert 40% of europe-west1 traffic to europe-west4 during degradation.",
        "model": "```hcl\nresource \"google_compute_backend_service\" \"payment_gateway_global\" {\n  name                  = \"payment-gateway-backend\"\n  project               = \"second-test-project-393510\"\n  protocol              = \"HTTP2\"\n  load_balancing_scheme = \"EXTERNAL_MANAGED\"\n\n  backend {\n    group                 = google_compute_region_network_endpoint_group.europe_west1_neg.id\n    balancing_mode        = \"RATE\"\n    max_rate_per_endpoint = 800\n    capacity_scaler       = 0.60 # Sheds 40% traffic during regional latency incident\n  }\n\n  backend {\n    group                 = google_compute_region_network_endpoint_group.europe_west4_neg.id\n    balancing_mode        = \"RATE\"\n    max_rate_per_endpoint = 1200\n    capacity_scaler       = 1.00 # Absorbs degraded overflow\n  }\n}\n```\n\n* **Status**: Tested and verified. Zero connection drops during synthetic regional drain."
      }
    ]
  },
  {
    "id": "session-4-ai-summit-research",
    "summary": "Deep Research: The AI Summit 2026 Enterprise Strategy & Architecture",
    "createdTime": "2026-09-04T07:00:00Z",
    "lastModifiedTime": "2026-09-04T07:00:00Z",
    "lastUserInputTime": "2026-09-04T07:00:00Z",
    "trajectoryMetadata": {
      "createdAt": "2026-09-04T07:00:00Z",
      "projectId": "second-test-project"
    },
    "turns": [
      {
        "user": "/deep-research-owl Research The AI Summit 2026 conference (New York & London). Conduct an executive-level architectural deep dive using the Universal Solution Architect and Six Thinking Hats frameworks: analyze major summit tracks (Agentic AI Summit, Generative AI Summit, Implement AI), keynote enterprise trends (production agentic workflows, sensitivity-aware model routing, sovereign AI in Europe), and formulate a boardroom-ready 6-Pillar Google Cloud leapfrog architecture for enterprise attendees.",
        "model": "# Enterprise Architecture Strategy: The AI Summit 2026 & Autonomous Agentic Workflows\n\n## 1. Executive Summary & Dual Grounding\n* **Target Scope**: Architectural synthesis of **The AI Summit 2026** (New York Dec 9\u201310, 2026 at Javits Center; London June 10\u201311, 2026 at Tobacco Dock, celebrating its 10th Anniversary). Focus on enterprise transition from static chatbots to autonomous multi-agent production swarms.\n* **Core Summit Tracks Evaluated**:\n  1. **The Agentic AI Summit**: Multi-agent orchestration, sensitivity-aware semantic routing, autonomous agent evaluation, and human-in-the-loop audit gates.\n  2. **The Generative AI Summit**: Enterprise ROI, cost-per-query optimization, and production retrieval architectures.\n  3. **Implement AI & European Sovereign Cloud**: Compliance with EU AI Act, strict data residency, and confidential computing.\n* **SSOT Citations**:\n  - Vertex AI Model Garden Specification: [file://google3/learning/genai/beyond/sdk/python/beyond_client.py#L45-82]\n  - BigLake Vector Search Protocol: [file://google3/cloud/biglake/v1/vector_search.proto#L20-65]\n  - Buganizer Tracking Reference: [b/535124194]\n\n## 2. Visual Architecture & Ingestion Topology\n```mermaid\ngraph TD\n    Client[\"Enterprise Client & Web Portal\"] -->|\"mTLS / HTTPS Ingress\"| Gateway[\"Cloud Run Ingress Gateway (:8080)\"]\n    Gateway -->|\"Payload Inspection\"| Router[\"Dynamic Sensitivity-Aware Router\"]\n    Router -->|\"Low-Latency / High-Throughput Tier\"| Lite[\"Vertex AI: Gemini 3.5 Flash Lite\"]\n    Router -->|\"Complex Reasoning & Code Tier\"| Flash[\"Vertex AI: Gemini 3.6 Flash / Gemini 3.5 Pro\"]\n    Lite -->|\"Federated Vector & Tool Calls\"| Memory[\"BigQuery Lakehouse & Vertex Vector Search\"]\n    Flash -->|\"Federated Vector & Tool Calls\"| Memory\n    Memory -->|\"Audit Trail & Lineage\"| Logging[\"Cloud Operations & Security Command Center\"]\n```\n\n## 3. SKU-Level Resource Allocation & Framework Cost Matrix\n| SKU Family / Component | Monthly List Spend | GCLM Contract Discount | Net Effective Spend | Architectural Purpose |\n| :--- | :--- | :--- | :--- | :--- |\n| **Cloud Run Ingress Gateway** | USD 240.00 | 25.0% GCLM Discount | USD 180.00 | Serverless edge API gateway, zero scale-to-zero cost |\n| **Vertex AI: Gemini 3.5 Flash Lite** | USD 1,450.00 | 20.0% GCLM Discount | USD 1,160.00 | Ultra-fast routing, extraction, and PII masking |\n| **Vertex AI: Gemini 3.6 Flash / Pro** | USD 3,800.00 | 20.0% GCLM Discount | USD 3,040.00 | Multi-step agentic planning, synthesis, and code generation |\n| **BigQuery Lakehouse & Vector Search** | USD 2,100.00 | 18.0% GCLM Discount | USD 1,722.00 | Zero-copy vector search, customer telemetry analytics |\n| **Cloud Operations Suite & Audit** | USD 320.00 | 15.0% GCLM Discount | USD 272.00 | End-to-end distributed tracing, tokenomics telemetry |\n\n## 4. Production-Grade Copy-Pasteable Script\n```bash\n#!/usr/bin/env bash\nset -euo pipefail\necho \"==> Deploying The AI Summit 2026 Enterprise Agentic Stack...\"\n\nPROJECT_ID=\"second-test-project-393510\"\nREGION=\"europe-west1\"\nGATEWAY_SERVICE=\"ai-summit-agentic-gateway\"\n\n# 1. Enable Required GCP APIs\ngcloud services enable \\\n  run.googleapis.com \\\n  aiplatform.googleapis.com \\\n  bigquery.googleapis.com \\\n  secretmanager.googleapis.com \\\n  --project=\"${PROJECT_ID}\"\n\n# 2. Configure Cloud Run Ingress Gateway with Sensitivity-Aware Routing\ngcloud run deploy \"${GATEWAY_SERVICE}\" \\\n  --image=\"gcr.io/${PROJECT_ID}/agentic-gateway:v3.1\" \\\n  --platform=managed \\\n  --region=\"${REGION}\" \\\n  --allow-unauthenticated \\\n  --set-env-vars=\"DEFAULT_ROUTING_MODEL=gemini-3.5-flash-lite,REASONING_MODEL=gemini-3.6-flash,PROJECT_ID=${PROJECT_ID}\" \\\n  --concurrency=80 \\\n  --min-instances=0 \\\n  --max-instances=20 \\\n  --project=\"${PROJECT_ID}\"\n\necho \"==> Deployment verified. Gateway operational in ${REGION}.\"\n```\n\n## 5. 360-Degree Six Hats SRE Risk Matrix\n* \u26aa **White Hat (Empirical Grounding)**: Real-time telemetry proves dual-tier routing (Flash Lite + Flash) cuts inference latency from 1.85s to 240ms.\n* \ud83d\udfe1 **Yellow Hat (Strategic ROI)**: Unlocks 46.2% net TCO savings compared to monolithic frontier model routing; payback achieved within 60 days.\n* \u26ab **Black Hat (SRE Bottlenecks)**: Downstream quota bursts on reasoning tokens; mitigated via exponential jittered backoff and regional failover buffers.\n* \ud83d\udd34 **Red Hat (DevEx & Empathy)**: Eliminates prompt sprawl; engineers define declarative tools instead of brittle monolithic system prompts.\n* \ud83d\udfe2 **Green Hat (10x Leapfrog Innovation)**: Combines in-memory semantic cache with BigQuery BigLake zero-copy vector search to eliminate data movement fees.\n* \ud83d\udd35 **Blue Hat (Executive Verdict)**: **VERDICT: GO**. Recommended reference blueprint for enterprise attendees at The AI Summit."
      },
      {
        "user": "Evaluate the European Sovereign AI and data residency requirements discussed at The AI Summit London, and specify the zero-trust compliance architecture on Google Cloud.",
        "model": "### \ud83c\uddea\ud83c\uddfa European Sovereign AI Architecture & Compliance Blueprint\n\nAt The AI Summit London, European enterprise leaders (spanning financial services, healthcare, and public sector) identified three non-negotiable sovereignty imperatives under the EU AI Act:\n\n1. **Strict Data Residency**: All customer embeddings, inference prompts, and output cache must reside within EU geographical boundaries (`europe-west3` Frankfurt and `europe-west1` Belgium).\n2. **Cryptographic Key Sovereignty**: Customer-Managed Encryption Keys (CMEK) backed by external Cloud EKM (Thales / Fortanix) where keys never leave EU jurisdiction.\n3. **Confidential Model Execution**: Hardware-attested confidential computing (AMD SEV-SNP) preventing hypervisor-level data inspection.\n\n#### \ud83d\udee1\ufe0f Sovereign Zero-Trust Topology\n* **VPC Service Controls (VPC-SC)**: Strict service perimeter encircling BigQuery, Vertex AI, and Cloud Storage, blocking all cross-border egress.\n* **Confidential GKE Autopilot**: Model inference workers deployed with `--enable-confidential-nodes` in `europe-west3`.\n* **Zero Model Training**: Verification of Google's Enterprise Privacy Guarantee ensuring zero customer data is used for foundation model training."
      }
    ]
  }
];

  var summariesMap = {};
  var trajectoriesMap = {};

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
      stepCount: stepsList.length,
      trajectoryId: s.id,
      cascadeId: s.id,
      status: 1,
      createdTime: s.createdTime,
      lastModifiedTime: s.lastModifiedTime,
      lastUserInputTime: s.lastUserInputTime,
      trajectoryType: 0,
      projectId: 'second-test-project',
      trajectoryMetadata: s.trajectoryMetadata,
      workspaces: [{ workspaceUri: 'file:///home/admin_mgenchev_altostrat_com/second-test-project' }]
    };

    trajectoriesMap[s.id] = {
      trajectoryId: s.id,
      cascadeId: s.id,
      trajectoryType: 0,
      projectId: 'second-test-project',
      trajectoryMetadata: s.trajectoryMetadata,
      workspaces: [{ workspaceUri: 'file:///home/admin_mgenchev_altostrat_com/second-test-project' }],
      steps: stepsList
    };
  });

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
        var activeCid = 'session-1-business-briefing';
        try {
          var matchActive = window.location.pathname.match(/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|session-[0-9]-[a-z-]+)/i);
          if (matchActive) activeCid = matchActive[0];
        } catch (e) {}

        return makeStreamWithInitialMessage({
          appState: {
            agentOnboardingCompleted: 2,
            postOnboarding: { completedSteps: [] },
            seenNuxs: { uids: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23] },
            lastSelectedAgentModel: savedModel,
            activeTrajectoryId: activeCid,
            sidebarSections: [
              {
                uri: 'second-test-project',
                label: 'second-test-project',
                sectionKind: {
                  case: 'projectSection',
                  value: {}
                },
                displayState: {
                  isCollapsed: false
                },
                conversations: [
                  { conversationId: 'session-1-business-briefing', title: 'Executive Briefing & Workspace Automation', lastModifiedTime: '2026-09-04T07:30:00Z' },
                  { conversationId: '3404756b-8ab0-45e1-b7c1-a31a2edb6572', title: 'BigQuery Live Analytics: Enterprise Cloud Spend & Telemetry', lastModifiedTime: '2026-09-04T07:20:00Z' },
                  { conversationId: 'session-3-agentic-sre', title: 'Agentic SRE: Regional Incident RCA & Circuit Breaker', lastModifiedTime: '2026-09-04T07:10:00Z' },
                  { conversationId: 'session-4-ai-summit-research', title: 'Deep Research: The AI Summit 2026 Enterprise Strategy & Architecture', lastModifiedTime: '2026-09-04T07:00:00Z' }
                ]
              }
            ]
          },
          userConfig: {}
        });
      }

      if (url.indexOf('JetboxSubscribeToSummaries') !== -1 || url.indexOf('jetboxSubscribeToSummaries') !== -1) {
        return makeStreamWithInitialMessage({
          summaries: summariesMap,
          updates: summariesMap
        });
      }

      if (url.indexOf('GetAllCascadeTrajectories') !== -1 || url.indexOf('getAllCascadeTrajectories') !== -1) {
        return makeGrpcWeb({
          trajectorySummaries: summariesMap,
          trajectories: Object.values(trajectoriesMap)
        });
      }

      var prewarmedIds = new Set([
        'session-1-business-briefing',
        'session-3-agentic-sre',
        'session-4-ai-summit-research'
      ]);

      var uuidToPrewarmed = {
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c81': 'session-1-productivity',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c82': 'session-2-cloud-ops',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c83': 'session-3-bigquery',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c84': 'session-4-agentic-sre',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c85': 'session-5-deep-research',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c86': 'session-6-kg-grounding',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c87': 'session-7-swarms-aaak',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c88': 'session-8-autonomous-coding',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c89': 'session-9-vibe-coder',
        '72a5d3c7-0ce8-427c-8683-3d4eeb3928cd': '72a5d3c7-0ce8-427c-8683-3d4eeb3928cd',
        'e3042b26-eed6-4c85-84fd-775f20d23d7e': 'e3042b26-eed6-4c85-84fd-775f20d23d7e',
        '3404756b-8ab0-45e1-b7c1-a31a2edb6572': '3404756b-8ab0-45e1-b7c1-a31a2edb6572',
        'c0729e55-1fa5-466d-b84f-8c9698f4bce1': 'c0729e55-1fa5-466d-b84f-8c9698f4bce1',
        '29906621-eb9a-42f5-ba0f-3760d24729fc': '29906621-eb9a-42f5-ba0f-3760d24729fc'
      };

      function resolvePrewarmedCid(args) {
        try {
          var reqBody = args[1] && args[1].body;
          if (reqBody) {
            var strBody = (typeof reqBody === 'string') ? reqBody : new TextDecoder().decode(reqBody);
            for (var pid of prewarmedIds) {
              if (strBody.indexOf(pid) !== -1) return pid;
            }
            for (var uid in uuidToPrewarmed) {
              if (strBody.indexOf(uid) !== -1) return uuidToPrewarmed[uid];
            }
          }
        } catch (e) {}

        try {
          var pathname = window.location.pathname || '';
          for (var pid of prewarmedIds) {
            if (pathname.indexOf(pid) !== -1) return pid;
          }
        } catch (e) {}

        try {
          var search = window.location.search || '';
          for (var pid of prewarmedIds) {
            if (search.indexOf(pid) !== -1) return pid;
          }
        } catch (e) {}

        return null;
      }

      if (url.indexOf('JetboxWriteSummary') !== -1 || url.indexOf('jetboxWriteSummary') !== -1) {
        try {
          var reqBody = args[1] && args[1].body;
          if (reqBody) {
            var str = (typeof reqBody === 'string') ? reqBody : new TextDecoder().decode(reqBody);
            var m = str.match(/\{.*\}/s);
            if (m) {
              var parsed = JSON.parse(m[0]);
              var s = parsed.summary || parsed;
              var id = s.cascadeId || s.trajectoryId || s.id;
              if (id) {
                summariesMap[id] = s;
                console.log('[Bootstrap] Registered live summary:', id, s.summary || s.title);
              }
            }
          }
        } catch (e) {}
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('StreamAgentStateUpdates') !== -1 || url.indexOf('streamAgentStateUpdates') !== -1) {
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid) {
          console.log('[Bootstrap] Serving pre-warmed StreamAgentStateUpdates for:', prewarmedCid);
          var targetTraj = trajectoriesMap[prewarmedCid];
          var stepsList = targetTraj.steps;

          return makeStreamWithInitialMessage({
            update: {
              conversationId: prewarmedCid,
              trajectoryId: prewarmedCid,
              status: 1,
              executableStatus: 1,
              executorLoopStatus: 1,
              fullyIdle: true,
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
          });
        }

        console.log('[Bootstrap] Live conversation detected - passing StreamAgentStateUpdates through to language server');
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('UpdateConversationAnnotations') !== -1 || url.indexOf('updateConversationAnnotations') !== -1) {
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid) {
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
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid) {
          var targetSummary = summariesMap[prewarmedCid];
          var ann = (targetSummary && targetSummary.annotations) ? targetSummary.annotations : {};
          return makeGrpcWeb({ annotations: ann });
        }
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('GetCascadeTrajectory') !== -1 || url.indexOf('getCascadeTrajectory') !== -1) {
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid && trajectoriesMap[prewarmedCid]) {
          var targetTraj = trajectoriesMap[prewarmedCid];
          return makeGrpcWeb({
            trajectory: targetTraj,
            status: 1,
            numTotalSteps: targetTraj.steps.length
          });
        }
        // Fallback: check if request body mentions any session in trajectoriesMap
        try {
          var reqBody = args[1] && args[1].body;
          if (reqBody) {
            var bStr = (typeof reqBody === 'string') ? reqBody : new TextDecoder().decode(reqBody);
            for (var tid in trajectoriesMap) {
              if (bStr.indexOf(tid) !== -1) {
                return makeGrpcWeb({
                  trajectory: trajectoriesMap[tid],
                  status: 1,
                  numTotalSteps: trajectoriesMap[tid].steps.length
                });
              }
            }
          }
        } catch (e) {}
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('GetCascadeTrajectorySteps') !== -1 || url.indexOf('getCascadeTrajectorySteps') !== -1) {
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid) {
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
            projectIds: ['second-test-project']
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
            userEmail: 'admin@mgenchev.altostrat.com',
            username: 'admin_mgenchev_altostrat_com',
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
