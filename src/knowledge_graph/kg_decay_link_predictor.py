#!/usr/bin/env python3
"""
Continuous Spaced Half-Life Decay & Adamic-Adar Link Predictor for Antigravity Web Hub.
Calculates:
1. Ebbinghaus temporal confidence decay: C(e, t) = C_0 * exp(-lambda * delta_t)
2. Structural edge prediction via Adamic-Adar index: AA(u, v) = sum_{z in N(u) cap N(v)} 1 / log(|N(z)|)
"""

import os
import sys
import json
import math
import time
import argparse
from collections import defaultdict
from typing import Dict, List, Any

DEFAULT_GRAPH_PATHS = [
    os.path.expanduser(os.environ.get("KG_JSON_PATH", "/mnt/data/knowledge_graph.json")),
    os.path.expanduser("~/.gemini/antigravity/knowledge_graph.json"),
    os.path.expanduser("~/Projects/Jarvis/knowledge_graph.json")
]

def find_active_graph_path() -> str:
    for path in DEFAULT_GRAPH_PATHS:
        if os.path.exists(path):
            return path
    return DEFAULT_GRAPH_PATHS[0]

def compute_adamic_adar_scores(graph_data: Dict[str, Any], score_threshold: float = 0.60) -> List[Dict[str, Any]]:
    nodes = {n["id"]: n for n in graph_data.get("nodes", []) if "id" in n}
    adj = defaultdict(set)
    
    for e in graph_data.get("edges", []):
        s, t = e.get("source"), e.get("target")
        if s and t:
            adj[s].add(t)
            adj[t].add(s)

    predicted_edges = []
    node_ids = list(nodes.keys())

    for i in range(len(node_ids)):
        u = node_ids[i]
        for j in range(i + 1, len(node_ids)):
            v = node_ids[j]
            if v in adj[u]:
                continue
            shared_neighbors = adj[u].intersection(adj[v])
            if not shared_neighbors:
                continue

            aa_score = sum(1.0 / math.log(len(adj[z])) for z in shared_neighbors if len(adj[z]) > 1)
            if aa_score >= score_threshold:
                confidence = round(1.0 - math.exp(-aa_score), 4)
                predicted_edges.append({
                    "source": u,
                    "target": v,
                    "relation": "relates_to",
                    "weight": confidence,
                    "properties": {
                        "predicted_by": "adamic_adar",
                        "aa_score": round(aa_score, 4),
                        "confidence": confidence
                    }
                })

    return predicted_edges

def apply_temporal_decay(graph_data: Dict[str, Any], half_life_days: float = 30.0) -> int:
    now = time.time()
    decay_lambda = math.log(2.0) / (half_life_days * 86400.0)
    decayed_count = 0

    for n in graph_data.get("nodes", []):
        props = n.setdefault("properties", {})
        c_0 = props.get("confidence", props.get("confidence_score", 1.0))
        updated_iso = n.get("updated_at") or props.get("updated_at")
        
        if updated_iso:
            try:
                ts = time.mktime(time.strptime(str(updated_iso)[:19], "%Y-%m-%dT%H:%M:%S"))
                delta_t = max(0.0, now - ts)
                decayed = c_0 * math.exp(-decay_lambda * delta_t)
                props["decayed_confidence"] = round(decayed, 4)
                decayed_count += 1
            except Exception:
                pass

    return decayed_count

def run_optimization(graph_path: str = None, predict: bool = True, decay: bool = True) -> Dict[str, Any]:
    active_path = graph_path or find_active_graph_path()
    if not os.path.exists(active_path):
        return {"status": "error", "message": f"Graph file not found at {active_path}"}

    with open(active_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    results = {"status": "ok", "graph_path": active_path}
    if predict:
        predictions = compute_adamic_adar_scores(graph_data)
        results["predicted_edges_count"] = len(predictions)
        results["predicted_edges"] = predictions
        
        # Add new predicted edges with confidence threshold
        existing_pairs = {(e["source"], e["target"]) for e in graph_data.get("edges", [])}
        added = 0
        for p in predictions:
            if (p["source"], p["target"]) not in existing_pairs:
                graph_data.setdefault("edges", []).append(p)
                existing_pairs.add((p["source"], p["target"]))
                added += 1
        results["added_edges_count"] = added

    if decay:
        decayed_nodes = apply_temporal_decay(graph_data)
        results["decayed_nodes_count"] = decayed_nodes

    graph_data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(active_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2)

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Adamic-Adar Link Predictor & Decay Engine")
    parser.add_argument("--predict", action="store_true", default=True, help="Predict missing structural edges")
    parser.add_argument("--decay", action="store_true", default=True, help="Apply confidence score half-life decay")
    parser.add_argument("--graph-path", type=str, default=None, help="Custom path to knowledge_graph.json")
    args = parser.parse_args()

    res = run_optimization(graph_path=args.graph_path, predict=args.predict, decay=args.decay)
    print(json.dumps(res, indent=2))
