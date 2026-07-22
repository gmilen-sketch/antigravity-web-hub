#!/usr/bin/env python3
"""
Knowledge Graph Memory Initializer for Antigravity Web Hub.
Bootstraps initial long-term memory graph schema, seeds core architectural entities, and warms shared-memory cache.
"""

import os
import sys
import json
import time

DEFAULT_OUTPUT_PATH = os.path.expanduser(os.environ.get("KG_JSON_PATH", "/mnt/data/knowledge_graph.json"))
FALLBACK_OUTPUT_PATH = os.path.expanduser("~/.gemini/antigravity/knowledge_graph.json")
WARM_CACHE_PATH = "/dev/shm/kg_warm_cache.json"

CORE_ENTITIES = [
    ("infra:n4_compute_vm", "Google Cloud N4 VM", "infrastructure", "5th Gen Intel Xeon Emerald Rapids compute engine hosting Antigravity Web Hub."),
    ("infra:hyperdisk_balanced", "Hyperdisk Balanced", "infrastructure", "High-performance block storage backend attached to N4 compute instance."),
    ("infra:classic_https_lb", "GCP Classic HTTPS Load Balancer", "infrastructure", "Public ingress load balancer terminating SSL and enforcing IAP zero-trust authentication."),
    ("model:gemini_3_5_flash", "Gemini 3.5 Flash", "model", "Ultra-low-latency default reasoning model served via Vertex AI streaming SSE."),
    ("model:gemini_3_1_pro", "Gemini 3.1 Pro", "model", "Deep reasoning model for multi-stage research and complex architectural analysis."),
    ("mcp:knowledge_graph", "Knowledge Graph Long-Term Memory", "mcp_server", "FastMCP memory engine providing 0ms shared-memory reads and graph context injection."),
    ("mcp:deep_research", "On-Demand Deep Research", "mcp_server", "FastMCP server executing multi-agent research loops over internal and external docs."),
    ("mcp:google_workspace", "Google Workspace MCP", "mcp_server", "Native Node.js MCP server connecting Drive, Docs, Sheets, and Gmail.")
]

CORE_EDGES = [
    ("infra:n4_compute_vm", "infra:hyperdisk_balanced", "attaches_storage", 1.0),
    ("infra:classic_https_lb", "infra:n4_compute_vm", "routes_traffic_to", 1.0),
    ("infra:n4_compute_vm", "model:gemini_3_5_flash", "streams_inference_from", 1.0),
    ("infra:n4_compute_vm", "mcp:knowledge_graph", "executes_module", 1.0),
    ("infra:n4_compute_vm", "mcp:deep_research", "executes_module", 1.0),
    ("infra:n4_compute_vm", "mcp:google_workspace", "executes_module", 1.0)
]

def init_knowledge_graph(target_path=None, force=False):
    if not target_path:
        target_path = DEFAULT_OUTPUT_PATH if os.path.exists(os.path.dirname(DEFAULT_OUTPUT_PATH)) else FALLBACK_OUTPUT_PATH

    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)

    if os.path.exists(target_path) and not force:
        print(f"[KG] Knowledge graph already exists at {target_path}. Skipping initialization.")
        return target_path

    nodes = []
    for nid, label, ntype, desc in CORE_ENTITIES:
        nodes.append({
            "id": nid,
            "label": label,
            "type": ntype,
            "description": desc,
            "properties": {"created_by": "bootstrap"},
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        })

    edges = []
    for src, dst, rel, w in CORE_EDGES:
        edges.append({
            "source": src,
            "target": dst,
            "relation": rel,
            "weight": w
        })

    payload = {
        "version": "1.0",
        "initialized_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": nodes,
        "edges": edges
    }

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except PermissionError:
        target_path = FALLBACK_OUTPUT_PATH
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    print(f"[KG] Successfully initialized Knowledge Graph at {target_path} ({len(nodes)} nodes, {len(edges)} edges).")

    # Warm shared memory cache
    try:
        if os.path.exists("/dev/shm") and os.access("/dev/shm", os.W_OK):
            with open(WARM_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            print(f"[KG] Shared-memory cache pre-warmed at {WARM_CACHE_PATH}.")
    except Exception as e:
        print(f"[KG] Warning: could not write /dev/shm cache: {e}")

    return target_path

if __name__ == "__main__":
    force_flag = "--force" in sys.argv
    init_knowledge_graph(force=force_flag)
