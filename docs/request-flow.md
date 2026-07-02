# Request flow — one Claude turn, byte-level

Walkthrough of a single user message picking Claude Opus 4.8, invoking the
`fetch_url` tool once, and rendering back into the SPA.

## 1. Page load (once per browser tab)

- Browser hits `https://<hostname>/`.
- GCP LB → jumpstation `:443` → nginx `:8080` → `location /` → proxy.py `:8082`.
- proxy.py fetches `/` from language_server `:8081`, decompresses gzip,
  finds `</head>`, injects our `<script>` block right before it. This block:
  1. Reads `localStorage.__selectedModelLabel` (fallback `"Gemini 3.5 Flash"`).
  2. Registers a `document.addEventListener('click', …, true)` capture-phase
     handler that catches clicks on popover option buttons whose text matches
     a known model label.
  3. Wraps `window.fetch` to add `x-user-model: <label>` on cascade RPCs.
  4. Installs a `MutationObserver` that force-repaints the model chip label
     whenever the SPA tries to revert it (locks for 5 s after user click).

## 2. StartCascade (browser → proxy)

- SPA generates a new conversation UUID, POSTs to
  `/exa.language_server_pb.LanguageServerService/StartCascade`
  (unary Connect, `application/grpc-web+json`).
- Our fetch wrapper attaches `x-user-model: Claude Opus 4.8`.
- nginx routes `/exa.*` unary paths through to proxy.py `:8082`
  (streaming paths go direct to language_server; StartCascade is unary).
- proxy.py sees `user_model in CLAUDE_MODELS` → Claude shim path:
  - Registers `CLAUDE_CASCADES[cid] = { model_label, trajectory_id,
    execution_id, created_at, turns: [] }`.
  - Persists a JSON snapshot to
    `/mnt/data/antigravity/claude_cascades/{cid}.json`.
  - Returns `{"cascadeId": cid}` as a grpc-web+json unary response with a
    `grpc-status: 0` trailer frame.

## 3. StreamAgentStateUpdates opens (browser → proxy, long-lived)

- SPA opens the state stream for `cid`. Stream RPCs are in nginx's streaming
  allowlist, but our Claude shim also intercepts this at proxy.py so it can
  serve synthetic frames — nginx doesn't include this specific RPC in its
  passthrough regex, so it goes through proxy.py.
- proxy.py's `StreamingResponse` yields an initial synthetic `CascadeAgentState`
  frame (empty turns), then polls `entry` every 500 ms, emitting a new frame
  whenever `(turn, response, tool_status, len(tool_history))` changes.
- Frame shape verified against the SPA's `Sba` merger:
  `stepsUpdate.{indices, steps, totalLength, pageBounds}` +
  `mainTrajectoryUpdate.parentReferences: []`.

## 4. SendUserCascadeMessage

User types *"Fetch https://example.com and tell me the h1 text"* and presses Enter.

- SPA POSTs `SendUserCascadeMessage` with `{ cascadeId, items: [{text: …}] }`.
- Wrapper attaches `x-user-model: Claude Opus 4.8`.
- proxy.py:
  1. Appends `{prompt, response: null}` to `entry["turns"]`.
  2. Persists the entry (turn 1 snapshot on disk).
  3. Fires the Vertex call as an `asyncio.create_task` (returns 200 immediately).
  4. Response back to SPA: enveloped empty JSON body + `grpc-status: 0` trailer.

## 5. Vertex Anthropic call (proxy → Vertex)

- `_call_vertex_claude(entry)` builds the full `messages` list from
  `entry["turns"]` (all prior user/assistant turns + current user prompt).
- POST to
  `https://aiplatform.googleapis.com/v1/projects/$PROJECT/locations/global/publishers/anthropic/models/claude-opus-4-8:rawPredict`
  with:
  - `Authorization: Bearer <ADC token>` (from `google-auth`)
  - `x-goog-user-project: $PROJECT`
  - Body: `{messages, max_tokens: 8192, tools: CLAUDE_TOOLS, anthropic_version: "vertex-2023-10-16"}`
  - `CLAUDE_TOOLS` includes `fetch_url`, `web_search`, and — if MCP is
    running — `deep_research`.

- Response contains `content: [{type: "tool_use", name: "fetch_url", id, input: {url: "https://example.com"}}]`.

## 6. Tool execution loop

- proxy.py appends the assistant `tool_use` block to `messages`.
- Sets `entry["tool_status"] = "Fetching https://example.com"` → polling
  stream picks this up and emits an in-progress `PLANNER_RESPONSE` step
  showing `⏳ Fetching https://example.com`.
- `_fetch_url(url)`:
  - SSRF guard: resolves `example.com`, rejects if any resolved IP is in
    `10/8`, `172.16/12`, `192.168/16`, `169.254/16` (blocks GCP metadata),
    `127/8`, or `::1`.
  - `httpx.AsyncClient` GET with browser UA.
  - Strips HTML → plain text via `html.parser` (drops `<script>/<style>`,
    keeps `<a href>` as `text (url)`).
  - Truncates to 40k chars.
- Appends `{type: "tool_result", tool_use_id, content: fetched_text}` to
  `messages` as a user role.
- Loop iteration 2: POST to Vertex again with the augmented messages.
- Response is text only (no more tool_use). Extract text via `_extract_text`.

## 7. Response back to the SPA

- `entry["turns"][-1]["response"] = text`.
- `entry["tool_status"] = None`.
- Persists to disk.
- Polling stream (step 3) sees `response` change → emits a new frame with a
  DONE `PLANNER_RESPONSE` step containing the answer.
- SPA's `Uba` merger picks up `mainTrajectoryUpdate.stepsUpdate`, replaces
  the in-progress step with the DONE step; React re-renders the message.

## 8. Persistence check

- Restart `antigravity-web.service`.
- `_load_cascades_from_disk()` reads every `*.json` under
  `/mnt/data/antigravity/claude_cascades/`, restores `CLAUDE_CASCADES`,
  re-attaches `model_config` from the label.
- `JetboxSubscribeToSummaries` hook emits synthetic summaries for every
  restored cascade → SPA sidebar shows them.
- User picks one → new `SendUserCascadeMessage` on the existing cid →
  proxy sticky-routes to Claude (because the cid is already in
  `CLAUDE_CASCADES`), even if the model chip has reset to Gemini.

## What doesn't happen

- No proto encoding/decoding of the Claude payload — Anthropic's Vertex API
  is HTTP+JSON, so proxy.py only touches JSON.
- No dependency on any Google-internal binary or endpoint (see
  ARCHITECTURE.md § *Antigravity binaries in use*).
