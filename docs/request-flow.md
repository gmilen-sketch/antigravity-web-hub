# Request flow — one Gemini turn, byte-level

Walkthrough of a single user message picking Gemini 3.5 Flash, invoking model inference via Vertex AI, and streaming responses back natively.

## 1. Page load (once per browser tab)

- Browser hits `https://<hostname>/`.
- GCP LB → jumpstation `:443` → nginx `:8080` → `location /` → Go `language_server` `:8081`.
- Nginx intercepts the HTML response and uses its `sub_filter` feature to inject our onboarding bypass `<script>` block directly into the `<head>` of the page on the fly:
  ```html
  <script>
    window.nativeStorage = {
      _d: { "antigravityOnboarding": "true", "antigravityUnifiedStateSync.onboarding": "true", "antigravity.isLoggedIn": "true" },
      getItems: async function(k) { ... },
      updateItems: async function(i) { ... },
      onChanged: function(c) { ... }
    };
  </script>
  ```
- This completely prevents the local client-side onboarding blocks without touching the underlying React assets.

## 2. GetUserStatus (browser → sidecar)

- When the SPA loads, it requests `/exa.language_server_pb.LanguageServerService/GetUserStatus` (unary, `application/grpc-web+json`).
- Nginx intercepts this exact path and proxies it to `ccpa_mock.py` on port `8083`.
- `ccpa_mock.py`:
  1. Passes the request to the Go `language_server` on port `8081` to fetch the real, live status response.
  2. Augments the response payload to include our custom model dropdown entries: **Gemini 3.5 Flash**, **Gemini 3.1 Flash Lite Preview**, and **Gemini 3.1 Pro** with their respective wire enums.
  3. Returns the augmented gRPC-Web payload back to the browser.
- The SPA reads `clientModelConfigs` and renders our custom options in the picker seamlessly.

## 3. StartCascade (browser → sidecar)

- When a new chat conversation starts, the SPA POSTs to `/exa.language_server_pb.LanguageServerService/StartCascade`.
- Nginx intercepts this path and proxies it to `ccpa_mock.py` on port `8083`.
- `ccpa_mock.py` parses the requested model from the payload, overrides the request with a valid root-level `requestedModel` enum that the Go backend's protobuf parser expects, and passes the modified request to `language_server` on port `8081`.
- `language_server` initializes the cascade and returns `{"cascadeId": cid}` with a standard gRPC-Web response.

## 4. SendUserCascadeMessage & StreamAgentStateUpdates (browser → Go direct)

- The user submits a prompt. The browser POSTs `SendUserCascadeMessage` and opens the long-lived `StreamAgentStateUpdates(cid)` stream.
- Since these are streaming endpoints and do not require sidecar intervention, Nginx maps them to the default catch-all paths and routes them **natively and directly** to `language_server` on port `8081` via `grpc_pass` and `proxy_pass`.
- This ensures absolute minimum latency, avoids any intermediate buffer delays, and utilizes Google's highly optimized Go server.

## 5. Model Inference interception (Go → sidecar → Vertex AI)

- The Go `language_server` (running with `--model_api_client_type=ccpa` and pointing `--cloud_code_endpoint` to `http://127.0.0.1:8083`) processes the message, wraps the request parameters into a Cloud Code model call, and makes a POST call to `http://127.0.0.1:8083/v1internal:streamGenerateContent?alt=sse`.
- Our sidecar `ccpa_mock.py` on port `8083` intercepts this stream request:
  1. Parses the payload and maps the requested model enum to the official Vertex AI model name (e.g., `gemini-3.5-flash` or `gemini-3.1-pro-preview`).
  2. Cleans the payload to retain only Vertex-compatible keys (e.g., `contents`, `systemInstruction`, `generationConfig`, `tools`, `toolConfig`), removing incompatible fields like `thinkingConfig` to prevent API errors.
  3. Obtains a fresh Google Application Default Credentials (ADC) Bearer token.
  4. Makes an asynchronous chunk-by-chunk HTTP stream request to the official Vertex AI global endpoint:
     ```
     https://aiplatform.googleapis.com/v1beta1/projects/{GCP_PROJECT}/locations/global/publishers/google/models/{model}:streamGenerateContent?alt=sse
     ```
  5. As chunked SSE tokens are returned by Vertex AI, `ccpa_mock.py` streams them directly back to `language_server` on port `8081`.

## 6. Response render

- `language_server` receives the streamed tokens from the sidecar, performs its internal orchestrations (including triggering any configured Workspace or local MCP tools natively), and streams the final results back to the browser via the open `StreamAgentStateUpdates` gRPC-Web connection.
- The browser renders the response in the React UI in real-time.
