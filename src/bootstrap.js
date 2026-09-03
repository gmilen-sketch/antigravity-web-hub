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
    'selectedWorkspaceUri': 'file:///home/admin_mgenchev_altostrat_com',
    'openProjects': JSON.stringify(['file:///home/admin_mgenchev_altostrat_com']),
    'recentProjects': JSON.stringify(['file:///home/admin_mgenchev_altostrat_com']),
    'lastOpenedWorkspace': 'file:///home/admin_mgenchev_altostrat_com'
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

  var PREWARMED_DEMO_SESSIONS = [
  {
    "id": "session-1-productivity",
    "summary": "Gmail Summary & Action Item Extraction",
    "createdTime": "2026-09-02T22:10:00Z",
    "lastModifiedTime": "2026-09-02T22:12:00Z",
    "turns": [
      {
        "user": "Summarize my recent project emails from the last 24 hours, identify critical action items, and draft a quick update reply for the team regarding our upcoming milestone.",
        "model": "### \ud83d\udcec Executive Email Briefing (Last 24 Hours)\n\n**1. SiteGround C4D GPU Capacity Allocation** (Elena Stanescu)\n* Status: Horizon allocation approved for `europe-west1` and `asia-southeast1`.\n* Action: Validate regional quota buffer before EOD.\n\n**2. BigQuery Conversational PoC Questions** (Horia Nicolescu)\n* Status: Received 12 test query sets from business stakeholders.\n* Action: Run baseline accuracy benchmark against `synthetic_analytics`.\n\n**3. Belgrade AI Tech Summit Keynote Slide Polish** (Milen Genchev)\n* Status: Presentation draft finalized on Global Anycast LB.\n* Action: Live stage walk-through.\n\n---\n### \u2709\ufe0f Drafted Team Update Reply\n```text\nTeam,\n\nQuick milestone sync: Horizon GPU capacity is confirmed for EU/APAC regions, and BigQuery benchmark test cases are loaded into the evaluation pipeline. We are fully on track for this week's milestone review.\n\nBest,\nMilen\n```"
      },
      {
        "user": "Send the drafted update reply to the account team and schedule a calendar sync for tomorrow at 10:00 AM CET.",
        "model": "\u2705 **Workspace Actions Executed**:\n1. \u2709\ufe0f **Dispatched Email**: Sent milestone update to `<TARGET_CUSTOMER_NAME> Account Team`.\n2. \ud83d\udcc5 **Calendar Invite Created**: `SiteGround Milestone Sync` scheduled for tomorrow, 10:00 AM \u2013 10:30 AM CET with Google Meet room provisioned.\n3. \ud83d\udccb **Task Logged**: Added action item to Google Tasks (`Validate regional quota buffer`)."
      }
    ]
  },
  {
    "id": "session-2-cloud-ops",
    "summary": "GCP Resource & Architecture Inspection",
    "createdTime": "2026-09-02T22:11:00Z",
    "lastModifiedTime": "2026-09-02T22:13:00Z",
    "turns": [
      {
        "user": "List all active Compute Engine instances, Cloud Run services, and BigQuery datasets in second-test-project-393510, and verify regional network security compliance.",
        "model": "### \u2601\ufe0f GCP Project Resource & Security Audit (`second-test-project-393510`)\n\n#### \ud83d\udda5\ufe0f Compute Engine Instances\n* `antigravity-ge-hub` | Zone: `us-central1-c` | Type: `c2-standard-16` (16 vCPUs, 64 GB) | IP: `10.0.1.4` (Internal Only)\n\n#### \ud83c\udf10 Global Ingress & Load Balancing\n* `antigravity-web-http-fr` (Port 80 Anycast: `34.160.89.22`)\n* Backend Service: `antigravity-web-backend` -> GCE VM Instance Group (:8080)\n\n#### \ud83d\udcca BigQuery Datasets\n1. `synthetic_analytics` (3 tables: `support_cases`, `cloud_billing_summary`, `api_traffic_telemetry`)\n2. `synthetic_ecommerce_orders` (1 table: `orders`)\n3. `Workspace_Logs_Syntetic` (1 table: `workspace_activity`)\n\n#### \ud83d\udee1\ufe0f Network Security & Compliance\n* [PASS] Zero public IP on backend VM substrate (Ingress isolated to Global L7 LB).\n* [PASS] Private Google Access enabled on VPC subnet `10.0.1.0/24`.\n* [PASS] Cross-region network bleed check: 0 unauthorized egress routes detected."
      },
      {
        "user": "Verify that the firewall rules strictly block external SSH and enforce Google Cloud IAP proxy access.",
        "model": "\ud83d\udee1\ufe0f **Firewall & Ingress Rule Verification**:\n* Rule `allow-iap-proxy`: **PASS** (TCP 22, 8080, 8081 allowed strictly from CIDR `35.235.240.0/20`).\n* Default Ingress Deny: **PASS** (Zero external 0.0.0.0/0 ingress permissions on management ports).\n* Host Integrity: Cloud Armor WAF policy attached to Global External HTTP Load Balancer."
      }
    ]
  },
  {
    "id": "session-3-bigquery",
    "summary": "BigQuery Sales & Customer Care Deep Dive",
    "createdTime": "2026-09-02T22:12:00Z",
    "lastModifiedTime": "2026-09-02T22:14:00Z",
    "turns": [
      {
        "user": "Query the synthetic_analytics and synthetic_ecommerce_orders BigQuery datasets to find our top revenue countries, correlate order volume with customer support ticket volume, and output a clean SQL query with visualizations.",
        "model": "### \ud83d\udcca BigQuery Revenue & Support Correlation Analysis\n\n```sql\nSELECT \n  o.country,\n  COUNT(DISTINCT o.order_id) AS total_orders,\n  ROUND(SUM(o.amount_usd), 2) AS gross_revenue_usd,\n  COUNT(DISTINCT s.case_id) AS support_cases_opened,\n  ROUND(COUNT(DISTINCT s.case_id) * 100.0 / COUNT(DISTINCT o.order_id), 2) AS case_rate_pct\nFROM `second-test-project-393510.synthetic_ecommerce_orders.orders` o\nLEFT JOIN `second-test-project-393510.synthetic_analytics.support_cases` s\n  ON o.customer_id = s.customer_id\nGROUP BY o.country\nORDER BY gross_revenue_usd DESC\nLIMIT 5;\n```\n\n#### \ud83d\udcc8 Result Dataset\n| Country | Total Orders | Gross Revenue (USD) | Support Cases | Case Rate | Health Status |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n| **United States** | 1,420 | $482,910.50 | 48 | 3.38% | \ud83d\udfe2 Optimal |\n| **Germany** | 890 | $298,440.00 | 29 | 3.25% | \ud83d\udfe2 Optimal |\n| **United Kingdom**| 760 | $245,120.00 | 38 | 5.00% | \ud83d\udfe1 Moderate |\n| **Japan** | 620 | $210,800.00 | 14 | 2.25% | \ud83d\udfe2 Optimal |\n| **Bulgaria** | 510 | $178,650.00 | 11 | 2.15% | \ud83d\udfe2 Optimal |\n\n**Key Takeaway**: Customer care volume scales linearly with order revenue ($R^2 = 0.94$). No abnormal churn spikes detected."
      },
      {
        "user": "Isolate the support cases in the United Kingdom with case_rate_pct of 5.00% to identify the primary category of tickets.",
        "model": "\ud83d\udd0d **UK Support Category Distribution**:\n* **Payment Processing / VAT Invoicing**: 22 cases (57.9%) \u2014 related to new HMRC digital tax compliance checks.\n* **Shipping / Courier Delays**: 11 cases (28.9%).\n* **Product Returns**: 5 cases (13.2%).\n\n**Recommendation**: Add automated VAT certificate generation at checkout to reduce UK support overhead by ~55%."
      }
    ]
  },
  {
    "id": "session-4-agentic-sre",
    "summary": "Vertex AI Latency Spike Root Cause Analysis",
    "createdTime": "2026-09-02T22:13:00Z",
    "lastModifiedTime": "2026-09-02T22:15:00Z",
    "turns": [
      {
        "user": "Analyze the api_traffic_telemetry dataset in BigQuery for error spikes (HTTP 429/500), compute p95 and p99 latency across regions, and isolate the root cause with remediation steps.",
        "model": "### \ud83d\udea8 Site Reliability Engineering (SRE) Incident Diagnosis\n\n#### \ud83d\udce1 Regional Latency & Error Distribution\n| Region | Total Requests | HTTP 200 | HTTP 429 | HTTP 500 | p50 Latency | p95 Latency | p99 Latency |\n| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n| `us-central1` | 450,210 | 99.82% | 0.15% | 0.03% | 142 ms | 310 ms | 480 ms |\n| `europe-west1`| 320,150 | 99.79% | 0.18% | 0.03% | 158 ms | 340 ms | 510 ms |\n| `asia-southeast1`| 185,400 | 94.10% | **5.80%** | 0.10% | 210 ms | **1,420 ms** | **2,850 ms** |\n\n#### \ud83d\udd0d Root Cause Analysis (RCA)\n* **Issue**: Rate-limit contention (HTTP 429) on Vertex AI regional quota in `asia-southeast1` caused connection queue buildup, escalating p99 latency to 2.85s.\n* **Remediation Plan**:\n  1. Activate dynamic cross-region overflow routing to `asia-northeast1`.\n  2. Enable client-side exponential jittered backoff interceptor.\n  3. Request quota expansion via Horizon Capacity planner."
      },
      {
        "user": "Simulate applying cross-region overflow routing and estimate post-mitigation p99 latency.",
        "model": "\ud83d\ude80 **Cross-Region Overflow Simulation Results**:\n* Routing 60% of `asia-southeast1` peak load to `asia-northeast1` Vertex AI endpoints.\n* **Projected Metrics**:\n  - HTTP 429 Errors: **0.00%** (eliminated)\n  - Regional p50: **162 ms** (-22.8%)\n  - Regional p95: **380 ms** (-73.2%)\n  - Regional p99: **440 ms** (**-84.6% reduction**)\n* Circuit breaker status: Healthy (CLOSED)."
      }
    ]
  },
  {
    "id": "session-5-deep-research",
    "summary": "Cloud Run vs GKE Autopilot Benchmark (6 Hats)",
    "createdTime": "2026-09-02T22:14:00Z",
    "lastModifiedTime": "2026-09-02T22:16:00Z",
    "turns": [
      {
        "user": "/deep-research-owl Perform a deep architectural comparison between Cloud Run and GKE Autopilot for high-concurrency LLM inference gateways, evaluating cold start latencies, autoscaling limits, and TCO using the Six Thinking Hats framework.",
        "model": "### \ud83e\udd89 Deep Research Owl: Cloud Run vs. GKE Autopilot for LLM Inference Gateways\n\n```\n+-----------------------------------------------------------------------------------------+\n|                         SIX THINKING HATS DECISION MATRIX                               |\n+-------------------+-----------------------------------+---------------------------------+\n| Perspective (Hat) | Cloud Run (Direct Concurrency)    | GKE Autopilot (Daemon Pods)     |\n+-------------------+-----------------------------------+---------------------------------+\n| \u26aa White (Data)    | Cold start: 850ms | Max scale: 2k | Cold start: 12s | Max scale: 5k |\n| \ud83d\udd34 Red (Intuition)| Ultra-simple DX, zero pod ops     | Familiar Kubernetes primitives  |\n| \u26ab Black (Risks)  | Max request timeout 60min; GPU $  | Complex node autoscaling curves |\n| \ud83d\udfe1 Yellow (Pros)  | 0 scale-to-zero cost, fast deploy | Custom Envoy filters, ALTS/mTLS |\n| \ud83d\udfe2 Green (Innov.) | Sidecar MCP containers in 1 serv  | Dynamic GPU slicing (NVIDIA MPS)|\n| \ud83d\udd35 Blue (Verdict) | Best for API Gateways & RAG       | Best for Raw Model Serving      |\n+-------------------+-----------------------------------+---------------------------------+\n```\n\n**Strategic Recommendation**: Use Cloud Run as the edge API & MCP proxy gateway ($850\\text{ ms}$ cold start, zero idle cost) fronting a dedicated GKE Autopilot cluster for heavy TPU/GPU LLM inference pipelines."
      },
      {
        "user": "Calculate the monthly TCO break-even point in queries per second where GKE Autopilot becomes cheaper than Cloud Run.",
        "model": "\ud83d\udcca **TCO Break-Even Sensitivity Model**:\n* **Variables**: Cloud Run vCPU/RAM per second vs. GKE Autopilot Pod vCPU/RAM + CUD 3-year commitment.\n* **Break-Even Crossover**: **38.4 QPS** (sustained 24/7).\n  - Below 38.4 QPS: Cloud Run scale-to-zero saves $1,420/month.\n  - Above 38.4 QPS: GKE Autopilot with 3-year committed use discount saves $2,180/month."
      }
    ]
  },
  {
    "id": "session-6-kg-grounding",
    "summary": "Deterministic Infrastructure Topology Resolution",
    "createdTime": "2026-09-02T22:15:00Z",
    "lastModifiedTime": "2026-09-02T22:17:00Z",
    "turns": [
      {
        "user": "Check the operational topology and compute cluster status across second-test-project-393510 using deterministic Knowledge Graph traversal and verify active VM endpoints.",
        "model": "### \ud83e\udde0 Deterministic Knowledge Graph Traversal Report\n* **Traversal Engine**: PreInvocation Shared-Memory Hook (`/dev/shm/kg_warm_cache.json`)\n* **Resolution Latency**: $0.38\\text{ ms}$ (Sub-millisecond deterministic lookup)\n\n```mermaid\ngraph TD\n    Project[second-test-project-393510] --> Network[VPC: default / 10.0.1.0/24]\n    Network --> VM[VM: antigravity-ge-hub / 10.0.1.4]\n    VM --> Port8080[Nginx Reverse Proxy :8080]\n    VM --> Port8081[Language Server :8081]\n    VM --> Port8083[CCPA Mock Gateway :8083]\n    VM --> Port8084[FastMCP Autonomy Hub :8084]\n    Project --> LB[Global External HTTP LB: 34.160.89.22]\n    LB --> Port8080\n```\n\n* **Verdict**: All 4 microservices healthy. Zero entity drift between configuration and live substrate."
      },
      {
        "user": "Probe each service port locally and verify process uptime and memory footprint.",
        "model": "\ud83d\udda5\ufe0f **Substrate Process Health Matrix**:\n* `:8080` (Nginx): PID 782 | Memory: 14.2 MB | Uptime: 48h 12m | Status: ACTIVE\n* `:8081` (Language Server): PID 16141 | Memory: 228.9 MB | Uptime: 24h 05m | Status: ACTIVE\n* `:8083` (CCPA Mock): PID 16204 | Memory: 42.1 MB | Uptime: 24h 05m | Status: ACTIVE\n* `:8084` (FastMCP Hub): PID 16230 | Memory: 38.6 MB | Uptime: 24h 05m | Status: ACTIVE"
      }
    ]
  },
  {
    "id": "session-7-swarms-aaak",
    "summary": "3-Agent Swarm with AAAK 3-Pass Compression",
    "createdTime": "2026-09-02T22:16:00Z",
    "lastModifiedTime": "2026-09-02T22:18:00Z",
    "turns": [
      {
        "user": "Dispatch a 3-agent swarm to inspect our telemetry logs, profile regional latency, and execute AAAK 3-pass context compression on the execution trace.",
        "model": "### \ud83d\udc1d Multi-Agent Swarm Execution & Context Optimization\n\n#### 1. Leaf Subagent Dispatches\n* `agent_1` (*Telemetry Auditor*): Scanned 450k log entries across BigQuery partitions.\n* `agent_2` (*Latency Profiler*): Generated p50/p95/p99 latency distributions.\n* `agent_3` (*Compression Engine*): Executed AAAK (Action-Aware Adaptive Knowledge) pipeline.\n\n#### 2. AAAK 3-Pass Context Compression Metrics\n* **Raw Trace Volume**: $84,320\\text{ tokens}$\n* **Pass 1 ($C_1$ - Structural Pruning)**: Removed tool payload redundancy $\\to 46,370\\text{ tokens}$ ($-45.0\\%$)\n* **Pass 2 ($C_2$ - ACT-R Decay)**: Applied $B_i = \\ln \\sum t_k^{-0.5}$ recency weighting $\\to 25,290\\text{ tokens}$ ($-70.0\\%$ cumulative)\n* **Pass 3 ($C_3$ - Semantic Crystallization)**: Synthesized canonical XML memory state $\\to 6,410\\text{ tokens}$ (**$-92.4\\%$ total reduction**)\n* **Execution Duration**: $118\\text{ ms}$ with $100\\%$ semantic retrieval fidelity."
      },
      {
        "user": "Evaluate context retention fidelity by querying the compressed state for regional error anomalies.",
        "model": "\ud83c\udfaf **Context Retention Verification**:\n* Query: `Isolate HTTP 429 root causes in asia-southeast1`\n* Result: Retrieved exact regional quota exhaustion event and remediation steps without loss of error codes or timestamps.\n* Signal Retention Score: **1.00 / 1.00 (Lossless Semantic Fidelity)**."
      }
    ]
  },
  {
    "id": "session-8-autonomous-coding",
    "summary": "Resilient Distributed Retry Interceptor",
    "createdTime": "2026-09-02T22:17:00Z",
    "lastModifiedTime": "2026-09-02T22:19:00Z",
    "turns": [
      {
        "user": "Write a robust Python gRPC client interceptor with exponential jittered backoff, circuit breaking, and telemetry logging, and provide a self-contained unit test with 100% coverage.",
        "model": "### \ud83d\udee0\ufe0f Production-Grade Resilient gRPC Interceptor (`grpc_resilient_interceptor.py`)\n\n```python\nimport grpc\nimport time\nimport random\nimport logging\nfrom typing import Callable, Any\n\nclass ResilientUnaryClientInterceptor(grpc.UnaryUnaryClientInterceptor):\n    def __init__(self, max_retries: int = 4, base_backoff: float = 0.5, max_backoff: float = 8.0):\n        self.max_retries = max_retries\n        self.base_backoff = base_backoff\n        self.max_backoff = max_backoff\n        self.retryable_codes = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.RESOURCE_EXHAUSTED}\n\n    def intercept_unary_unary(self, continuation: Callable, client_call_details: Any, request: Any):\n        for attempt in range(1, self.max_retries + 1):\n            try:\n                response = continuation(client_call_details, request)\n                return response\n            except grpc.RpcError as rpc_err:\n                if rpc_err.code() not in self.retryable_codes or attempt == self.max_retries:\n                    logging.error(f\"[gRPC] Non-retryable error or max retries exceeded: {rpc_err.code()}\")\n                    raise rpc_err\n                \n                # Full Jitter Exponential Backoff\n                sleep_time = min(self.max_backoff, self.base_backoff * (2 ** (attempt - 1)))\n                jittered_sleep = random.uniform(0, sleep_time)\n                logging.warning(f\"[gRPC] Retry attempt {attempt}/{self.max_retries} in {jittered_sleep:.2f}s...\")\n                time.sleep(jittered_sleep)\n```\n\n#### \u2705 Unit Test Verification: 100% Pass Rate (5/5 tests passing in 0.04s)"
      },
      {
        "user": "Add circuit breaker state machine (CLOSED, OPEN, HALF_OPEN) with a 30s recovery window.",
        "model": "\u26a1 **Circuit Breaker Integrated**:\n* Added `CircuitBreakerState` tracking consecutive failures.\n* Threshold: 5 failures -> Transitions to `OPEN`.\n* Recovery: After 30s cooldown -> Transitions to `HALF_OPEN` to test downstream health with a single probe request.\n* All 8 unit tests passing with zero regressions."
      }
    ]
  }
];

  var summariesMap = {};
  var trajectoriesMap = {};

  PREWARMED_DEMO_SESSIONS.forEach(function(s) {
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
      trajectoryType: 0,
      workspaces: [{ workspaceUri: 'file:///home/admin_mgenchev_altostrat_com' }]
    };

    trajectoriesMap[s.id] = {
      trajectoryId: s.id,
      cascadeId: s.id,
      trajectoryType: 0,
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
        var activeCid = 'session-1-productivity';
        try {
          var matchActive = window.location.pathname.match(/session-[0-9]-[a-z-]+/);
          if (matchActive) activeCid = matchActive[0];
        } catch (e) {}

        return makeStreamWithInitialMessage({
          appState: {
            agentOnboardingCompleted: 2,
            postOnboarding: { completedSteps: [] },
            seenNuxs: { uids: [] },
            lastSelectedAgentModel: savedModel,
            activeTrajectoryId: activeCid,
            sidebarSections: [
              {
                uri: 'workspace-keynote-demos',
                label: 'Keynote Demonstrations',
                sectionKind: {
                  case: 'workspaceSection',
                  value: {
                    workspaceUri: 'file:///home/admin_mgenchev_altostrat_com',
                    folderUris: ['file:///home/admin_mgenchev_altostrat_com']
                  }
                },
                displayState: {
                  isCollapsed: false
                },
                conversations: PREWARMED_DEMO_SESSIONS.map(function(s) {
                  return {
                    conversationId: s.id,
                    title: s.summary,
                    lastModifiedTime: s.lastModifiedTime
                  };
                })
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
        'session-1-productivity',
        'session-2-cloud-ops',
        'session-3-bigquery',
        'session-4-agentic-sre',
        'session-5-deep-research',
        'session-6-kg-grounding',
        'session-7-swarms-aaak',
        'session-8-autonomous-coding'
      ]);

      var uuidToPrewarmed = {
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c81': 'session-1-productivity',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c82': 'session-2-cloud-ops',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c83': 'session-3-bigquery',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c84': 'session-4-agentic-sre',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c85': 'session-5-deep-research',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c86': 'session-6-kg-grounding',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c87': 'session-7-swarms-aaak',
        'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c88': 'session-8-autonomous-coding'
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
          return makeGrpcWeb({});
        }
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('FetchConversationAnnotations') !== -1 || url.indexOf('fetchConversationAnnotations') !== -1 ||
          url.indexOf('GetConversationAnnotations') !== -1 || url.indexOf('getConversationAnnotations') !== -1) {
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid) {
          return makeGrpcWeb({ annotations: {} });
        }
        return window._origNativeFetch.apply(this, args);
      }

      if (url.indexOf('GetCascadeTrajectory') !== -1 || url.indexOf('getCascadeTrajectory') !== -1) {
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid) {
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
        var prewarmedCid = resolvePrewarmedCid(args);
        if (prewarmedCid) {
          var targetTraj = trajectoriesMap[prewarmedCid];
          return makeGrpcWeb({
            steps: targetTraj.steps
          });
        }
        return window._origNativeFetch.apply(this, args);
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
      if (url.indexOf('RecordAnalyticsEvent') !== -1 || url.indexOf('recordAnalyticsEvent') !== -1) {
        return makeGrpcWeb({});
      }

      return window._origNativeFetch.apply(this, args);
    };
  }
})();
