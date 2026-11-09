---
okf_version: "0.2"
id: antigravity-cli-and-sdk
title: "Antigravity CLI v1.5.3 (agents-cli) & Python SDK (google-antigravity) Reference"
summary: "Developer reference for the Antigravity CLI v1.5.3, google-antigravity Python SDK (LocalAgentConfig, ATIF-v1.7 trajectories), hooks.json contract, PreInvocation injectSteps schema, and Harbor 3P benchmark execution."
type: reference
status: verified
confidence: 0.99
last_verified: "2026-11-09"
tags: [antigravity-cli, agents-cli, google-antigravity, sdk, hooks, harbor, atif, agentapi]
aliases: [antigravity cli, agents-cli, google-antigravity, antigravity-sdk, localagentconfig, hooks.json, injectsteps, rootconversationid]
related_concepts: [antigravity-web-hub-architecture, autonomy-lifecycle-governance, gemini-models-and-vertex-api, google-adk-and-a2a-protocol]
sources:
  - id: src-install
    type: code_repo
    title: "scripts/install.sh — Antigravity Core 2.29.1 & CLI 1.5.3 Installer"
    URI: "scripts/install.sh"
    fetched_at: "2026-11-09"
  - id: src-hooks-json
    type: code_repo
    title: "hooks.json & .antigravity-plugin/plugin.json — Plugin & Hook Schema"
    URI: "hooks.json"
    fetched_at: "2026-11-09"
---

# Antigravity CLI v1.5.3 (`agents-cli`) & Python SDK (`google-antigravity`) Reference

## 1. Antigravity Standalone CLI (`v1.5.3`) & Server Flags

* **Binary Locations (`scripts/install.sh`)**:
  - Companion CLI binary: `/usr/local/bin/antigravity` (`v1.5.3`, installed from `cli_linux_x64.tar.gz`) [^src-install].
  - Headless Web Hub server: `~/.gemini/antigravity/bin/language_server` (`v2.29.1`, launched with `--subclient_type=hub --override_ide_version="2.29.1" -standalone`) [^src-install].
* **Environment Controls (`config/start_hub.sh`)**:
  - `AGY_CLI_AUTO_COMPACT_OVERRIDE="80%"`: Triggers automatic context compaction at 80% context window utilization.
  - `GIT_PAGER="cat"` and `JJ_PAGER="cat"`: Prevents interactive TTY pagers from hanging background subshells.
  - `PYTHONSAFEPATH="1"` and `PYTHONDONTWRITEBYTECODE="1"`: Prevents local workspace modules from shadowing Python stdlib packages and suppresses `.pyc` bytecode generation.

## 2. Programmatic Python SDK (`google-antigravity`) & Evaluation Mode

When invoking the `google-antigravity` Python SDK inside automated workflows or Harbor 3P benchmark containers:
* **`LocalAgentConfig` & `.eval()` Preset**:
  - Configure headless benchmark execution via `LocalAgentConfig(**config_kwargs).eval()` (which defaults `thinking_level` to `"HIGH"` or reads `REASONING_EFFORT` from `"low"`, `"medium"`, `"high"`, `"extra_high"`, `"max"`).
  - Execute `agent.chat(instruction)` and export the trajectory in **ATIF-v1.7** format (`trajectory.json`).
* **Harbor 3P Container Flags**:
  - Always pass `-y` (non-interactive confirmation), `--jobs-dir "$HOME/jobs"` (outside network filesystems), `--override-gpus 0` (on CPU hosts), and `--allow-agent-host "generativelanguage.googleapis.com"` (when `allow_internet = false`).

## 3. Plugin Manifest (`.antigravity-plugin/plugin.json`) & `hooks.json` Contract

* **Plugin Manifest Schema (`plugin.json`)**:
  - Declares `"name"`, `"version"` (`"3.9.0"`), `"skills": "skills"`, `"agents": "agents"`, `"rules": "rules"`, `"hooks": "hooks.json"`, and `"mcpServers": "mcp_config.json"` [^src-hooks-json].
* **Strict Hook Payload & Output Schemas (`2026-10-13` Contract)**:
  1. **`PreInvocation` (`kg_pre_invocation_hook.py`)**: Reads `transcriptPath`, `rootConversationId`, and `prompt` from `stdin` JSON; must emit **only** `{"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]}` (`HookSystemMessage`) (or `{}`) on `stdout` (`enforce_strict_pre_invocation_schema`) [^src-hooks-json].
  2. **`PreToolUse` (`sentinel_dispatch.py`)**: Reads `toolName` (`tool_name`), `toolArgs` (`tool_input`), and `rootConversationId`; emits `{"decision": "allow"}` or `{"decision": "deny", "reason": "..."}`.
  3. **`Stop` (`agent_stop_black_hat_gate.py`)**: Reads `terminationReason`, `executionNum`, `transcriptPath`, `artifactDirectoryPath`, and `rootConversationId`; emits `{"decision": "allow"}` or `{"decision": "continue", "reason": "..."}`.

[^src-install]: Verified in `scripts/install.sh` and `config/start_hub.sh` (`v3.9.0`).
[^src-hooks-json]: Verified in `hooks.json`, `.antigravity-plugin/plugin.json`, and `src/hooks/kg_pre_invocation_hook.py` (`v3.9.0`).
