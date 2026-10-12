# Request flow — one Gemini or Claude turn, byte-level

Walkthrough of a single user message picking **Gemini 4 Argon (GA)**, **Gemini 3.8 Flash**, or **Claude Opus 5.5 / Sonnet 5.5 / Fable 5**, invoking model inference via Vertex AI, and streaming responses back natively.

## 1. Page load (once per browser tab)

- Browser hits `https://<hostname>/`.
- GCP LB → jumpstation `:443` → nginx `:8080` → `location /` → Go `language_server` `:8081`.
- Nginx intercepts the HTML response and uses its `sub_filter` feature to inject our `bootstrap.js` state-machine script directly into the `<head>` of the page on the fly.
- This bypasses local client-side onboarding blocks, hydrates cross-browser sidebar sessions from `/api/sessions`, and populates the 8-model selector without touching the underlying React assets.

## 2. GetUserStatus (browser → sidecar)

- When the SPA loads, it requests `/exa.language_server_pb.LanguageServerService/GetUserStatus` (unary, `application/grpc-web+json`).
- Nginx intercepts this exact path and proxies it to `ccpa_mock.py` on port `8083`.
- `ccpa_mock.py`:
  1. Passes the request to the Go `language_server` on port `8081` to fetch the real, live status response.
  2. Augments the response payload to include our 8-model GA dropdown entries: **Gemini 4 Argon** (`354`), **Gemini 3.8 Flash** (`352`), **Gemini 3.7 Flash** (`350`), **Gemini 3.6 Flash** (`348`), **Gemini 3.5 Flash Lite** (`330`), **Claude Opus 5.5 (Vertex AI)** (`290`), **Claude Sonnet 5.5 (Vertex AI)** (`333`), and **Claude Fable 5 (Next-Gen)** (`340`).
  3. Returns the augmented gRPC-Web payload back to the browser.
- The SPA reads `clientModelConfigs` and renders our custom options in the picker seamlessly.

## 3. StartCascade (browser → sidecar)

- When a new chat conversation starts, the SPA POSTs to `/exa.language_server_pb.LanguageServerService/StartCascade`.
- Nginx intercepts this path and proxies it to `ccpa_mock.py` on port `8083`.
- `ccpa_mock.py` parses the requested model from the payload, overrides the request with a valid root-level `requestedModel` enum that the Go backend's protobuf parser expects, and passes the modified request to `language_server` on port `8081`.
- `language_server` initializes the cascade and returns `{"cascadeId": cid}` with a standard gRPC-Web response.

## 4. SendUserCascadeMessage & StreamAgentStateUpdates (browser → Go direct + `/api/sessions`)

- The user submits a prompt. The browser POSTs `SendUserCascadeMessage`, persists the updated trajectory to `/api/sessions` (with monotonic step protection), and opens the long-lived `StreamAgentStateUpdates(cid)` stream.
- Since these are streaming endpoints, Nginx maps them to the default catch-all paths and routes them **natively and directly** to `language_server` on port `8081` via `grpc_pass` and `proxy_pass`.

## 5. Model Inference interception (Go → sidecar → Vertex AI)

- The Go `language_server` (running with `--model_api_client_type=ccpa` and pointing `--cloud_code_endpoint` to `http://127.0.0.1:8083`) processes the message, wraps the request parameters into a Cloud Code model call, and makes a POST call to `http://127.0.0.1:8083/v1internal:streamGenerateContent?alt=sse`.
- Our sidecar `ccpa_mock.py` on port `8083` intercepts this stream request:
  1. Parses the payload and maps the requested model enum to the official Vertex AI model ID (`gemini-4-argon`, `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `claude-opus-5-5`, `claude-sonnet-5-5`, or `claude-fable-5`).
  2. Sanitizes the payload (`sanitize_gemini_4_payload` strips `thinkingBudget`, `candidateCount`, `presencePenalty`, `frequencyPenalty`, and normalizes `thinkingLevel: MINIMAL` → `MEDIUM` for `gemini-4-argon`; translates Gemini content blocks into Anthropic Messages API `rawPredict` for Claude 5.5 / Fable 5).
  3. Obtains a fresh Google Application Default Credentials (ADC) Bearer token.
  4. Streams via Multi-Region Endpoint (`global` → `us` → `eu`) to Vertex AI (`aiplatform.googleapis.com`).
     ```
     https://aiplatform.googleapis.com/v1beta1/projects/{GCP_PROJECT}/locations/global/publishers/google/models/{model}:streamGenerateContent?alt=sse
     ```
  5. As chunked SSE tokens are returned by Vertex AI, `ccpa_mock.py` streams them directly back to `language_server` on port `8081`.

## 6. Response render

- `language_server` receives the streamed tokens from the sidecar, performs its internal orchestrations (including triggering any configured Workspace or local MCP tools natively), and streams the final results back to the browser via the open `StreamAgentStateUpdates` gRPC-Web connection.
- The browser renders the response in the React UI in real-time.
