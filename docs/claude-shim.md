# The CCPA Mock Sidecar (Replacement of the Claude Shim)

In previous versions, a complex reverse-proxy (`proxy.py`) ran a custom "Claude shim" to intercept user prompts and drive Anthropic models through Vertex AI via a custom Python-based multi-turn tool loop.

This legacy setup has been **fully retired** and replaced by a much cleaner, robust, and zero-latency architecture utilizing the Go `language_server`'s native Cloud Code Proxy Assistant (CCPA) interface and a lightweight sidecar (`ccpa_mock.py` on port `8083`).

---

## Why the Claude Shim was retired

The previous Claude shim approach had several critical architectural limitations:
1. **High latency and overhead:** Every single byte of traffic (including binary assets, large frontend bundles, and high-throughput streaming gRPC connections) had to pass through an intermediate FastAPI server, introducing latency and connection pool bottlenecks.
2. **Duplicate Orchestration:** The python proxy had to reinvent the wheel, implementing its own multi-turn message history, disk persistence, and tool execution loops (fetch, search, etc.) which are already natively and highly-optimized inside Google's Go-based `language_server`.
3. **Fragility:** Handling chunked HTTP/2 streaming proxies and grpc-web binary envelopes in Python FastAPI is notoriously brittle and prone to transport dropouts (`ERR_HTTP2_PROTOCOL_ERROR`).

---

## The New Way: The CCPA Mock Sidecar

In the new architecture, the Go `language_server` is started in CCPA client mode:
```bash
--model_api_client_type=ccpa
--cloud_code_endpoint=http://127.0.0.1:8083
```

Instead of proxying the entire world, we run a native Go server on port `8081` and intercept ONLY three specific things:

### 1. Model Dropdown Augmentation (`GetUserStatus`)
When the SPA requests `/exa.language_server_pb.LanguageServerService/GetUserStatus`, Nginx routes it to `ccpa_mock.py` on port `8083`. The sidecar calls Go's port `8081` to get the status, appends our custom Gemini models (`Gemini 3.5 Flash`, `Gemini 3.1 Flash Lite Preview`, `Gemini 3.1 Pro`) into the proto wire format, and returns it.

### 2. Session Initialization (`StartCascade`)
When a new chat starts, `/exa.language_server_pb.LanguageServerService/StartCascade` is intercepted by Nginx and routed to the sidecar to inject the appropriate default model and parameters, matching what the Go backend expects.

### 3. Native Model Execution (`streamGenerateContent`)
Because the Go `language_server` runs in CCPA mode, it natively drives all chat steps, user prompts, history preservation, and tool orchestrations. When it needs to call the model, it makes a POST request to `/v1internal:streamGenerateContent` on its configured endpoint (`http://127.0.0.1:8083`).

Our sidecar `ccpa_mock.py`:
- Intercepts this call.
- Resolves the model name to its official Vertex AI identifier (e.g. `gemini-3.5-flash`).
- Strips any incompatible settings from the generation configuration (such as `thinkingConfig` for standard models) to guarantee API compatibility.
- Attaches the local VM's Application Default Credentials (ADC) token.
- Forwards the stream directly to the official Google Vertex AI endpoints over standard Server-Sent Events (SSE).

This yields a robust, zero-latency, and zero-maintenance architecture that gets the best of both worlds: full Vertex AI integration and native Go gRPC execution.
