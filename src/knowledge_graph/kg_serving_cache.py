#!/usr/bin/env python3
"""Shared Memory Serving Cache Hydrator (`kg_serving_cache.py`).
Synchronizes the persistent Knowledge Graph JSON and OKF v0.2 (`kb/`) concept dossiers
into the 0ms shared memory serving cache (`/dev/shm/kg_warm_cache.json`).
Filters out provisional (`status == 'PROVISIONAL'`) and expired (`decayed_confidence < 0.15`)
`steer:*` preference nodes so only verified, active rules are served at runtime.
"""
import json
import os
import tempfile
import time
from typing import Any, Dict, List

WARM_CACHE_PATH = "/dev/shm/kg_warm_cache.json" if os.path.exists("/dev/shm") else "/tmp/kg_warm_cache.json"
STEER_SERVING_CONFIDENCE_FLOOR = 0.15


def filter_servable_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filters out provisional or decayed steer:* nodes before warming the serving cache."""
    servable: List[Dict[str, Any]] = []
    for n in nodes:
        nid = str(n.get("id", ""))
        if nid.startswith("steer:"):
            props = n.get("properties") or {}
            if props.get("status") == "PROVISIONAL" or props.get("active") is False:
                continue
            decayed = float(props.get("decayed_confidence", props.get("confidence", 1.0)))
            if decayed < STEER_SERVING_CONFIDENCE_FLOOR:
                continue
        servable.append(n)
    return servable


def hydrate_serving_cache(graph_path: str, cache_path: str = WARM_CACHE_PATH) -> Dict[str, Any]:
    """Atomically writes the unified serving cache from graph_path."""
    if not os.path.exists(graph_path):
        return {"status": "missing_source", "graph_path": graph_path}

    with open(graph_path, "r", encoding="utf-8") as f:
        graph = json.load(f)

    raw_nodes = graph.get("nodes", [])
    servable_nodes = filter_servable_nodes(raw_nodes)

    warm_data = {
        "version": graph.get("version", "2.0-OKF-v0.2"),
        "okf_version": "0.2",
        "updated_at": time.time(),
        "warmed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": servable_nodes,
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
        "filtered_out_count": len(raw_nodes) - len(servable_nodes),
        "edges_count": len(warm_data["edges"]),
    }


if __name__ == "__main__":
    from knowledge_graph.kg_decay_link_predictor import find_active_graph_path
    res = hydrate_serving_cache(find_active_graph_path())
    print(json.dumps(res, indent=2))
