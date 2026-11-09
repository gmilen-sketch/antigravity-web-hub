---
okf_version: "0.2"
id: google-adk-and-a2a-protocol
title: "Google Agent Development Kit (ADK / google-adk) & A2A Protocol Reference"
summary: "Developer reference for Google Agent Development Kit (google-adk Python SDK & CLI), multi-agent orchestration (LlmAgent, SequentialAgent, ParallelAgent, LoopAgent, McpToolset), Vertex AI Agent Engine deployment, and A2A JSON-RPC protocol schemas."
type: reference
status: verified
confidence: 0.99
last_verified: "2026-10-21"
tags: [adk, google-adk, a2a, agent2agent, llmagent, mcp-toolset, vertex-ai-agent-engine, multi-agent]
aliases: [adk, google-adk, agent development kit, llmagent, sequentialagent, parallelagent, loopagent, a2a protocol, agent2agent]
related_concepts: [antigravity-web-hub-architecture, gemini-models-and-vertex-api, antigravity-cli-and-sdk]
sources:
  - id: adk-oss-spec
    type: documentation
    title: "Google Agent Development Kit (google-adk) Open-Source Specification"
    URI: "https://google.github.io/adk-docs/"
    fetched_at: "2026-10-21"
  - id: a2a-oss-spec
    type: documentation
    title: "Agent2Agent (A2A) Open Protocol Specification"
    URI: "https://google.github.io/A2A/"
    fetched_at: "2026-10-21"
---

# Google Agent Development Kit (ADK / `google-adk`) & A2A Protocol Reference

## 1. Core `google-adk` Primitives & Python SDK (`pip install google-adk`)

The open-source **Google Agent Development Kit (`google-adk`)** provides code-first primitives for building, evaluating, and deploying single and multi-agent systems on Gemini and Vertex AI [^adk-oss-spec]:

* **`LlmAgent` (`from google.adk.agents import LlmAgent` / `Agent`)**:
  - Core reasoning agent configured with `name`, `model` (default `"gemini-3.8-flash"`), `instruction`, `description`, `tools=[...]`, `sub_agents=[...]`, and `output_key` (writes response into shared `session.state[output_key]`).
* **Deterministic Workflow Orchestrators (`from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent`)**:
  - `SequentialAgent(name=..., sub_agents=[...])`: Executes child agents in strict sequential pipeline order, passing shared `session.state`.
  - `ParallelAgent(name=..., sub_agents=[...])`: Executes independent child agents concurrently in isolated branches and merges state keys.
  - `LoopAgent(name=..., sub_agents=[...], max_iterations=N)`: Iteratively runs child agents until an escalation condition (`EventActions(escalate=True)`) or `max_iterations` is reached.
* **Tools & MCP Integration (`FunctionTool`, `McpToolset`, `AgentTool`)**:
  - Plain Python functions with typed parameters and docstrings are automatically wrapped as `FunctionTool(func)` (accepting optional `tool_context: ToolContext` for `tool_context.state` access).
  - `McpToolset(connection_params=StdioServerParameters(command=..., args=...))` connects any STDIO or SSE FastMCP server directly to an `LlmAgent`.
* **Runtime & Session Persistence (`Runner`, `InMemorySessionService`, `VertexAiSessionService`)**:
  - `Runner(agent=root_agent, app_name="...", session_service=InMemorySessionService())` executes `runner.run_async(user_id=..., session_id=..., new_message=...)` yielding streaming `Event` objects (`event.is_final_response()`).

## 2. `adk` CLI & `agents-cli` (`google-agents-cli`) Commands

* **`agents-cli` (`uv tool install google-agents-cli`)**:
  - `agents-cli info`: Inspects current ADK project configuration and active environment.
  - `agents-cli scaffold create <name>` / `agents-cli scaffold enhance .`: Scaffolds a new ADK agent project or enhances an existing repository.
  - `agents-cli run "<prompt>"`: Runs an interactive or single-shot prompt against the local ADK project.
* **`adk` CLI Commands**:
  - `adk run <agent_package_dir>`: Interactive terminal chat with a local ADK agent package (containing `__init__.py` and `agent.py` defining `root_agent`).
  - `adk web --port 8000`: Launches the local FastAPI + Dev UI trace inspector (`http://127.0.0.1:8000`).
  - `adk api_server --port 8080`: Starts a headless production FastAPI REST + SSE endpoint for the agent.
  - `adk eval <agent_package_dir> <eval_set.json>`: Evaluates tool-trajectory accuracy and response match scores.
* **Built-In Tool Imports, Callbacks & Live Docs Index (`https://adk.dev/llms.txt`)**:
  - Import ADK built-in tool instances directly from their submodule (`from google.adk.tools.load_web_page import load_web_page`), and use `before_agent_callback(callback_context: CallbackContext)` to initialize `callback_context.state`.
  - Fetch `https://adk.dev/llms.txt` (or `https://adk.dev/agents/models/google-gemini/index.md`) for live ADK documentation URLs.
* **Managed Deployment (`Vertex AI Agent Engine`)**:
  - Wrap `root_agent` in `vertexai.preview.reasoning_engines.AdkApp(agent=root_agent, enable_tracing=True)` and deploy via `vertexai.agent_engines.create(agent_engine=app, requirements=["google-cloud-aiplatform[adk,agent_engines]"])`.

## 3. Agent2Agent (`A2A`) Protocol Schema Invariants

When exposing an agent over the open **A2A (`Agent2Agent`)** protocol (`/.well-known/agent.json` and JSON-RPC `POST /a2a`) [^a2a-oss-spec]:
1. **Synchronous vs SSE Streaming Capability (`AgentCard.capabilities`)**:
   - If the A2A endpoint returns synchronous `application/json` responses, the Agent Card **must** declare `"capabilities": {"streaming": false}`. Declaring `"streaming": true` on a non-SSE endpoint causes A2A clients to reject responses expecting `Content-Type: text/event-stream`.
2. **`message/send` Result Schema Contract**:
   - The JSON-RPC `result` object for `message/send` must be a flat A2A `Message` object (`{"kind": "message", "messageId": "msg-...", "role": "agent", "parts": [{"kind": "text", "text": "..."}], "contextId": "..."}`) rather than a nested `{"message": {"role": "assistant"}}` wrapper.

[^adk-oss-spec]: Verified against Google ADK (`google-adk`) specification.
[^a2a-oss-spec]: Verified against Agent2Agent (`A2A`) JSON-RPC specification.
