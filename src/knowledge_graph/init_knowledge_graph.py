#!/usr/bin/env python3
"""
Knowledge Graph Memory Initializer for Antigravity Web Hub (v3.9.0 Clean-Room Edition).
Populates the Knowledge Graph by default with 100% public, zero-secret Foundational Reference
Documentation (Antigravity Web Hub self-documentation, Antigravity CLI v1.5.3 & Python SDK,
Google Agent Development Kit `google-adk` & `agents-cli`, Gemini 4 / 3.8 / 3.6 / 3.5 Flash & Claude 5.5
Vertex AI model contracts, and the 5 OKF v0.2 `kb/` reference dossiers), and warms the isolated
shared-memory serving cache (`/dev/shm/agw_kg_warm_cache.json`). Supports `empty=True`
(`--empty` / `AGW_EMPTY_KG=1`) to initialize a zero-node graph for null-control A/B benchmarks.
"""

import os
import sys
import json
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DEFAULT_KB_ROOT = os.path.join(REPO_ROOT, "kb")

DEFAULT_OUTPUT_PATH = os.path.expanduser(os.environ.get("KG_JSON_PATH", "/mnt/data/knowledge_graph.json"))
FALLBACK_OUTPUT_PATH = os.path.expanduser("~/.gemini/antigravity/knowledge_graph.json")
WARM_CACHE_PATH = os.environ.get("KG_WARM_CACHE_PATH", "/dev/shm/agw_kg_warm_cache.json")

FOUNDATIONAL_ENTITIES = [
    (
        "doc:antigravity_web_hub",
        "Antigravity Web Hub v3.9.0 Self-Documentation",
        "documentation",
        "4-plane runtime architecture: Nginx reverse proxy (:8080 + bootstrap.js), headless Go language_server v2.29.1 (:8081), 8-Model Vertex AI ADC router ccpa_mock.py (:8083), and 8 FastMCP servers (:8084) with /api/sessions persistence and /dev/shm/agw_kg_warm_cache.json.",
        ["antigravity web hub", "web hub", "ccpa_mock", "start_hub", "bootstrap.js", "language_server"],
        {"ports": "8080 (Nginx), 8081 (language_server v2.29.1), 8083 (ccpa_mock), 8084 (FastMCP)", "sessions_api": "GET/POST /api/sessions -> /mnt/data/projects/persistent_ui_sessions.json"},
    ),
    (
        "doc:antigravity_cli_sdk",
        "Antigravity CLI v1.5.3 & Python SDK (google-antigravity)",
        "documentation",
        "Companion CLI (/usr/local/bin/antigravity v1.5.3) and programmatic Python SDK (google-antigravity LocalAgentConfig().eval(), ATIF-v1.7 trajectories, hooks.json lifecycle contract, and Harbor 3P benchmark flags).",
        ["antigravity cli", "google-antigravity", "antigravity-sdk", "localagentconfig", "hooks.json", "rootconversationid", "agentapi"],
        {"cli_binary": "/usr/local/bin/antigravity (v1.5.3)", "env_vars": "AGY_CLI_AUTO_COMPACT_OVERRIDE=80%, GIT_PAGER=cat, JJ_PAGER=cat, PYTHONSAFEPATH=1, PYTHONDONTWRITEBYTECODE=1"},
    ),
    (
        "doc:google_adk",
        "Google Agent Development Kit (ADK / google-adk) & A2A Protocol",
        "documentation",
        "Open-source Python agent framework (pip install google-adk): LlmAgent, SequentialAgent, ParallelAgent, LoopAgent, FunctionTool, McpToolset, Runner, Vertex AI Agent Engine deployment, and Agent2Agent (A2A) JSON-RPC protocol.",
        ["adk", "google-adk", "agent development kit", "llmagent", "sequentialagent", "parallelagent", "loopagent", "mcp-toolset", "a2a protocol", "agent2agent"],
        {"cli_commands": "adk run, adk web --port 8000, adk api_server --port 8080, adk eval", "docs_index": "https://adk.dev/llms.txt", "a2a_contract": "Set capabilities.streaming=false for synchronous JSON-RPC; return flat Message object {'kind': 'message', 'role': 'agent', 'parts': [...]}"},
    ),
    (
        "doc:agents_cli",
        "Google Agents CLI (agents-cli / google-agents-cli)",
        "documentation",
        "Developer CLI for scaffolding, inspecting, and running ADK agent projects (`uv tool install google-agents-cli`): `agents-cli info`, `agents-cli scaffold create <name>`, `agents-cli scaffold enhance .`, and `agents-cli run \"<prompt>\"`.",
        ["agents-cli", "google-agents-cli", "scaffold create", "scaffold enhance", "agents cli"],
        {"install_cmd": "uv tool install google-agents-cli", "core_commands": "agents-cli info, agents-cli scaffold create <name>, agents-cli scaffold enhance ., agents-cli run"},
    ),
    (
        "doc:gemini_vertex_models",
        "Gemini & Vertex AI Model Catalog & API Parameter Contracts",
        "documentation",
        "8-Model GA catalog (Gemini 4 Argon enum 354, Gemini 3.8 Flash enum 352, Gemini 3.5 Flash enum 350, Gemini 3.6 Flash enum 348, Gemini 3.5 Flash Lite enum 330, Claude Opus/Sonnet 5.5 enums 290/333, Claude Fable 5 enum 340), embeddings/media/open models, and sanitize_gemini_4_payload() API rules.",
        ["gemini models", "model documentation", "vertex ai models", "sanitize_gemini_4_payload", "thinkinglevel", "thinkingconfig"],
        {"gemini_4_rules": "Strip thinkingBudget, candidateCount, frequencyPenalty, presencePenalty; normalize thinkingLevel MINIMAL->MEDIUM and MAX->HIGH", "embeddings_and_media": "gemini-embedding-001, gemini-embedding-2, imagen-3.0-generate-002, veo-3.1-lite, gemma-3, gemma-4-26b-a4b-it"},
    ),
    (
        "doc:autonomy_hooks_and_skills",
        "14-Pillar Clean-Room Autonomy Engine, 4 Hooks & 20 PD-Q Skills",
        "documentation",
        "Four deterministic hooks via run_hook_safe.sh (PreInvocation kg_pre_invocation_hook.py with HookSystemMessage + Dual-Mode SWE router + /dev/shm turn cache, PostInvocation black_hat_in_progress_ux_hook.py zero-token verification banner, PreToolUse sentinel_dispatch.py with force_ask + GOLDFISH-RO-1, Stop agent_stop_black_hat_gate.py v4.18 Adaptive K=1..3 [SHARD:<id>] Goldfish->Holistic Judge gate), 20 PD-Q skills, 5 subagents, and scripts/run_ab_benchmark.py.",
        ["autonomy engine", "lifecycle hooks", "pd-q skills", "black-hat-goldfish", "black-hat-judge", "dual-mode classifier", "run_ab_benchmark"],
        {"hooks": "PreInvocation (HookSystemMessage), PostInvocation (Zero-Token UX Banner), PreToolUse (Sentinel + force_ask + GOLDFISH-RO-1), Stop (v4.18 Adaptive K=1..3 Goldfish->Judge)", "benchmark_runner": "python3 -B scripts/run_ab_benchmark.py --self-test | --mode dual-daemon | --mode harbor"},
    ),
    (
        "model:gemini_4_argon",
        "Gemini 4 Argon",
        "model",
        "Flagship 1M-context GA reasoning model (proto enum 354 -> gemini-4-argon, 1,048,576 input / 131,072 output tokens) served via Vertex AI with sanitize_gemini_4_payload() parameter normalization.",
        ["gemini-4-argon", "gemini 4", "enum 354"],
        {"proto_enum": 354, "vertex_model_id": "gemini-4-argon", "context_window": 1048576, "max_output_tokens": 131072},
    ),
    (
        "model:gemini_3_8_flash",
        "Gemini 3.8 Flash",
        "model",
        "Recommended default production multimodal reasoning, agentic coding, and tool-dispatch model on Vertex AI (proto enum 352 -> gemini-3.8-flash, 1,048,576 input / 131,072 output tokens).",
        ["gemini-3.8-flash", "gemini 3.8 flash", "enum 352"],
        {"proto_enum": 352, "vertex_model_id": "gemini-3.8-flash", "context_window": 1048576, "max_output_tokens": 131072},
    ),
    (
        "model:gemini_3_5_flash",
        "Gemini 3.5 Flash",
        "model",
        "Long-GA production and EU regional data-residency multimodal synthesis model on Vertex AI (proto enum 350 -> gemini-3.5-flash, 1,048,576 input / 65,535 output tokens).",
        ["gemini-3.5-flash", "gemini 3.5 flash", "enum 350"],
        {"proto_enum": 350, "vertex_model_id": "gemini-3.5-flash", "context_window": 1048576, "max_output_tokens": 65535},
    ),
    (
        "model:gemini_3_6_flash",
        "Gemini 3.6 Flash",
        "model",
        "General production multimodal and parallel subagent swarm model on Vertex AI (proto enum 348 -> gemini-3.6-flash, 1,048,576 input / 131,072 output tokens).",
        ["gemini-3.6-flash", "gemini 3.6 flash", "enum 348"],
        {"proto_enum": 348, "vertex_model_id": "gemini-3.6-flash", "context_window": 1048576, "max_output_tokens": 131072},
    ),
    (
        "model:gemini_3_5_flash_lite",
        "Gemini 3.5 Flash Lite",
        "model",
        "High-throughput, low-latency classification and extraction model on Vertex AI (proto enum 330 -> gemini-3.5-flash-lite, 1,048,576 input / 65,536 output tokens).",
        ["gemini-3.5-flash-lite", "gemini 3.5 flash lite", "enum 330"],
        {"proto_enum": 330, "vertex_model_id": "gemini-3.5-flash-lite", "context_window": 1048576, "max_output_tokens": 65536},
    ),
    (
        "mcp:knowledge_graph",
        "Knowledge Graph Long-Term Memory FastMCP Server",
        "mcp_server",
        "FastMCP memory server (src/knowledge_graph/kg_mcp_server.py) providing 0ms shared-memory reads (/dev/shm/agw_kg_warm_cache.json), bitemporal entity storage, and OKF v0.2 dossier synchronization.",
        ["knowledge_graph", "kg_mcp_server", "agw_kg_warm_cache"],
        {"entry_point": "src/knowledge_graph/kg_mcp_server.py", "warm_cache": "/dev/shm/agw_kg_warm_cache.json"},
    ),
    (
        "mcp:autonomy_engine",
        "14-Pillar Autonomy Engine FastMCP Server",
        "mcp_server",
        "FastMCP server (src/autonomy_engine/autonomy_mcp_server.py) exposing P0/P1 circuit-breakers, 6-field BM25F + Graph-RAG polyphonic retrieval, Bayesian Self-Grill, Six Thinking Hats Delphi routing, and 14-mode evaluation.",
        ["autonomy_engine", "autonomy_mcp_server", "polyphonic_retriever", "p0_engine", "p1_engine"],
        {"entry_point": "src/autonomy_engine/autonomy_mcp_server.py", "eager_load": True},
    ),
]

FOUNDATIONAL_EDGES = [
    ("doc:antigravity_web_hub", "doc:antigravity_cli_sdk", "DOCUMENTS_RUNTIME", 1.0),
    ("doc:antigravity_web_hub", "doc:gemini_vertex_models", "ROUTES_MODELS", 1.0),
    ("doc:antigravity_web_hub", "doc:autonomy_hooks_and_skills", "ENFORCES_GOVERNANCE", 1.0),
    ("doc:antigravity_web_hub", "mcp:knowledge_graph", "HOSTS_MCP_SERVER", 1.0),
    ("doc:antigravity_web_hub", "mcp:autonomy_engine", "HOSTS_MCP_SERVER", 1.0),
    ("doc:google_adk", "doc:agents_cli", "SCAFFOLDED_BY", 1.0),
    ("doc:google_adk", "doc:gemini_vertex_models", "EXECUTES_ON_MODEL", 1.0),
    ("doc:google_adk", "mcp:autonomy_engine", "CONNECTS_VIA_MCP_TOOLSET", 0.95),
    ("doc:antigravity_cli_sdk", "doc:autonomy_hooks_and_skills", "INVOKES_HOOKS", 1.0),
    ("doc:gemini_vertex_models", "model:gemini_4_argon", "DEFINES_MODEL_SPEC", 1.0),
    ("doc:gemini_vertex_models", "model:gemini_3_8_flash", "DEFINES_MODEL_SPEC", 1.0),
    ("doc:gemini_vertex_models", "model:gemini_3_5_flash", "DEFINES_MODEL_SPEC", 1.0),
    ("doc:gemini_vertex_models", "model:gemini_3_6_flash", "DEFINES_MODEL_SPEC", 1.0),
    ("doc:gemini_vertex_models", "model:gemini_3_5_flash_lite", "DEFINES_MODEL_SPEC", 1.0),
]


def init_knowledge_graph(
    target_path=None,
    force=False,
    seed_demo=True,
    warm_cache_path=None,
    empty=False,
    kb_root=None,
):
    if not target_path:
        target_path = DEFAULT_OUTPUT_PATH if os.path.exists(os.path.dirname(DEFAULT_OUTPUT_PATH)) else FALLBACK_OUTPUT_PATH
    active_warm_cache = warm_cache_path or WARM_CACHE_PATH

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    if os.path.exists(target_path) and not force:
        print(f"[KG] Knowledge graph already exists at {target_path}. Skipping initialization.")
        return target_path

    force_empty = bool(empty or os.environ.get("AGW_EMPTY_KG") == "1" or (seed_demo is False))
    nodes = []
    edges = []
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    if not force_empty:
        for nid, label, ntype, desc, aliases, extra_props in FOUNDATIONAL_ENTITIES:
            props = {"created_by": "foundational_docs_seed", "confidence": 1.0, "base_confidence": 1.0}
            props.update(extra_props)
            nodes.append({
                "id": nid,
                "label": label,
                "type": ntype,
                "description": desc,
                "aliases": aliases,
                "properties": props,
                "updated_at": now_iso,
            })
        for src, dst, rel, w in FOUNDATIONAL_EDGES:
            edges.append({
                "source": src,
                "target": dst,
                "relation": rel,
                "weight": w,
            })

    payload = {
        "version": "2.0-OKF-v0.2",
        "initialized_at": now_iso,
        "nodes": nodes,
        "edges": edges,
    }

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except PermissionError:
        target_path = FALLBACK_OUTPUT_PATH
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    # Also compile OKF v0.2 reference dossiers (kb/) into the graph when not in empty mode
    active_kb = kb_root or DEFAULT_KB_ROOT
    if not force_empty and os.path.isdir(active_kb):
        try:
            from src.knowledge_graph.okf_knowledge_compiler import sync_kb_to_graph
        except ImportError:
            try:
                from knowledge_graph.okf_knowledge_compiler import sync_kb_to_graph
            except ImportError:
                sync_kb_to_graph = None
        if sync_kb_to_graph is not None:
            try:
                sync_kb_to_graph(kb_root=active_kb, graph_path=target_path)
                with open(target_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception:
                pass

    print(
        f"[KG] Successfully initialized Knowledge Graph at {target_path} "
        f"({len(payload.get('nodes', []))} nodes, {len(payload.get('edges', []))} edges)."
    )

    try:
        cache_dir = os.path.dirname(os.path.abspath(active_warm_cache))
        if os.path.exists(cache_dir) and os.access(cache_dir, os.W_OK):
            with open(active_warm_cache, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            print(f"[KG] Shared-memory cache pre-warmed at {active_warm_cache}.")
    except Exception as e:
        print(f"[KG] Warning: could not write shared-memory cache: {e}")

    return target_path


if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    empty_flag = "--empty" in sys.argv
    init_knowledge_graph(force=force_flag, seed_demo=not empty_flag, empty=empty_flag)
