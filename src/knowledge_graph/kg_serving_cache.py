#!/usr/bin/env python3
"""Shared Memory Serving Cache Hydrator (`kg_serving_cache.py`).
Synchronizes the persistent Knowledge Graph JSON and OKF v0.2 (`kb/`) concept dossiers
into the 0ms shared memory serving cache (`/dev/shm/kg_warm_cache.json`).
"""
import json
import os
import tempfile
import time
from typing import Any, Dict

WARM_CACHE_PATH = "/dev/shm/kg_warm_cache.json" if os.path.exists("/dev/shm") else "/tmp/kg_warm_cache.json"


def hydrate_serving_cache(graph_path: str, cache_path: str = WARM_CACHE_PATH) -> Dict[str, Any]:
    """Atomically writes the unified serving cache from graph_path."""
    if not os.path.exists(graph_path):
        return {"status": "missing_source", "graph_path": graph_path}

    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    warm_data = {
        "version": graph.get("version", "2.0-OKF-v0.2"),
        "okf_version": "0.2",
        "updated_at": time.time(),
        "warmed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": graph.get("nodes", []),
        "edges": graph.get("edges", []),
    }

    cache_dir = os.path.dirname(cache_path)
    os.makedirs(cache_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=cache_dir, delete=False, encoding="utf-8") as tf:
        json.dump(warm_data, tf)
        temp_name = tf.name
    os.replace(temp_name, cache_path)
    return {
        "status": "ok",
        "cache_path": cache_path,
        "nodes_count": len(warm_data["nodes"]),
        "edges_count": len(warm_data["edges"]),
    }


if __name__ == "__main__":
    from knowledge_graph.kg_decay_link_predictor import find_active_graph_path
    res = hydrate_serving_cache(find_active_graph_path())
    print(json.dumps(res, indent=2))
