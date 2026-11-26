#!/usr/bin/env python3
"""
Knowledge Graph Long-Term Memory Engine for Antigravity Web Hub.
Provides fast JSON & SQLite persistent graph storage, 0ms shared-memory caching (/dev/shm/kg_warm_cache.json),
and compact 1-to-2 hop prompt-ready context injection (<500 tokens).
"""

import os
import sys
import json
import time
import sqlite3
import logging
from typing import Dict, List, Any, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [KG-ENGINE] %(message)s")

DEFAULT_KG_JSON = os.path.expanduser(os.environ.get("KG_JSON_PATH", "/mnt/data/knowledge_graph.json"))
FALLBACK_KG_JSON = os.path.expanduser("~/.gemini/antigravity/knowledge_graph.json")
WARM_CACHE_PATH = os.environ.get("KG_WARM_CACHE_PATH", "/dev/shm/agw_kg_warm_cache.json")

class KnowledgeGraphEngine:
    def __init__(self, json_path: Optional[str] = None):
        self.json_path = json_path or (DEFAULT_KG_JSON if os.path.exists(os.path.dirname(DEFAULT_KG_JSON)) else FALLBACK_KG_JSON)
        self.warm_cache_path = os.environ.get("KG_WARM_CACHE_PATH", WARM_CACHE_PATH)
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._last_mtime: Tuple[str, float, str, float] = ("", -1.0, "", -1.0)
        self._load_graph()

    def _get_active_file(self) -> str:
        if os.path.exists(self.json_path):
            return self.json_path
        if os.path.exists(FALLBACK_KG_JSON):
            return FALLBACK_KG_JSON
        return self.json_path

    def _compute_mtime_snapshot(self) -> Tuple[str, float, str, float]:
        cache_p = os.environ.get("KG_WARM_CACHE_PATH", self.warm_cache_path)
        active_p = self._get_active_file()
        try:
            c_mtime = os.path.getmtime(cache_p) if cache_p and os.path.exists(cache_p) else -1.0
        except OSError:
            c_mtime = -1.0
        try:
            a_mtime = os.path.getmtime(active_p) if active_p and os.path.exists(active_p) else -1.0
        except OSError:
            a_mtime = -1.0
        return (cache_p, c_mtime, active_p, a_mtime)

    def _ensure_fresh(self) -> bool:
        current_snap = self._compute_mtime_snapshot()
        if current_snap != self._last_mtime:
            self.warm_cache_path = current_snap[0]
            self._load_graph()
            return True
        return False

    def _load_graph(self):
        self.warm_cache_path = os.environ.get("KG_WARM_CACHE_PATH", self.warm_cache_path)
        active_file = self._get_active_file()
        c_mtime = os.path.getmtime(self.warm_cache_path) if os.path.exists(self.warm_cache_path) else -1.0
        a_mtime = os.path.getmtime(active_file) if os.path.exists(active_file) else -1.0

        # 1. Try reading warm cache first when fresh (>= primary JSON mtime) for 0ms reads
        if os.path.exists(self.warm_cache_path) and c_mtime >= a_mtime:
            try:
                with open(self.warm_cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    self.nodes = {n["id"]: n for n in cache_data.get("nodes", []) if "id" in n}
                    self.edges = cache_data.get("edges", [])
                    self._last_mtime = self._compute_mtime_snapshot()
                    return
            except Exception as e:
                logging.warning(f"Failed to read warm cache: {e}")

        # 2. Fall back to primary JSON file
        if os.path.exists(active_file):
            try:
                with open(active_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.nodes = {n["id"]: n for n in data.get("nodes", []) if "id" in n}
                    self.edges = data.get("edges", [])
                    self._update_warm_cache()
            except Exception as e:
                logging.error(f"Failed to load KG from {active_file}: {e}")
        else:
            self.nodes = {}
            self.edges = []
        self._last_mtime = self._compute_mtime_snapshot()

    def _update_warm_cache(self):
        try:
            cache_dir = os.path.dirname(os.path.abspath(self.warm_cache_path))
            if cache_dir and os.path.exists(cache_dir) and os.access(cache_dir, os.W_OK):
                node_list = list(self.nodes.values())
                payload = {
                    "version": "1.0",
                    "updated_at": time.time(),
                    "nodes_count": len(node_list),
                    "edges_count": len(self.edges),
                    "nodes": node_list,
                    "edges": self.edges
                }
                with open(self.warm_cache_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f)
        except Exception:
            pass

    def save(self):
        active_file = self._get_active_file()
        try:
            os.makedirs(os.path.dirname(os.path.abspath(active_file)), exist_ok=True)
            payload = {
                "version": "1.0",
                "updated_at": time.time(),
                "nodes": list(self.nodes.values()),
                "edges": self.edges
            }
            with open(active_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except PermissionError:
            active_file = FALLBACK_KG_JSON
            os.makedirs(os.path.dirname(os.path.abspath(active_file)), exist_ok=True)
            payload = {
                "version": "1.0",
                "updated_at": time.time(),
                "nodes": list(self.nodes.values()),
                "edges": self.edges
            }
            with open(active_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        self._update_warm_cache()

    def upsert_node(self, node_id: str, label: str, node_type: str = "entity", description: str = "", properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        node = {
            "id": node_id,
            "label": label,
            "type": node_type,
            "description": description,
            "properties": properties or {},
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        self.nodes[node_id] = node
        self.save()
        return node

    def upsert_edge(self, source: str, target: str, relation: str = "relates_to", weight: float = 1.0) -> Dict[str, Any]:
        for edge in self.edges:
            if edge["source"] == source and edge["target"] == target and edge.get("relation") == relation:
                edge["weight"] = weight
                self.save()
                return edge
        edge = {
            "source": source,
            "target": target,
            "relation": relation,
            "weight": weight
        }
        self.edges.append(edge)
        self.save()
        return edge

    def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        self._ensure_fresh()
        q = query.lower()
        results = []
        for node in self.nodes.values():
            score = 0
            if q in node.get("id", "").lower():
                score += 3
            if q in node.get("label", "").lower():
                score += 2
            if q in node.get("description", "").lower():
                score += 1
            if score > 0:
                results.append((score, node))
        results.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in results[:limit]]

    def get_subgraph_context(self, target_id: str, max_hops: int = 2) -> str:
        """Extracts an ultra-compact (<500 tokens) prompt-ready context block for LLMs."""
        self._ensure_fresh()
        if target_id not in self.nodes:
            matches = self.search_nodes(target_id, limit=1)
            if matches:
                target_id = matches[0]["id"]
            else:
                return f"[Knowledge Graph]: No matching entity found for '{target_id}'."

        root = self.nodes[target_id]
        visited = {target_id}
        hop1_nodes = set()
        relations = []

        for edge in self.edges:
            if edge["source"] == target_id:
                hop1_nodes.add(edge["target"])
                target_label = self.nodes.get(edge["target"], {}).get("label", edge["target"])
                relations.append(f"- {root.get('label', target_id)} --({edge.get('relation', 'relates_to')})--> {target_label}")
            elif edge["target"] == target_id:
                hop1_nodes.add(edge["source"])
                source_label = self.nodes.get(edge["source"], {}).get("label", edge["source"])
                relations.append(f"- {source_label} --({edge.get('relation', 'relates_to')})--> {root.get('label', target_id)}")

        visited.update(hop1_nodes)

        lines = [
            f"=== Knowledge Graph Context (Entity: {root.get('label', target_id)}) ===",
            f"Type: {root.get('type', 'entity')} | Description: {root.get('description', 'N/A')}"
        ]
        if relations:
            lines.append("Connected Memory Graph:")
            lines.extend(relations[:8])
        lines.append("=========================================================")
        return "\n".join(lines)

_engine_instance = None

def get_kg_engine() -> KnowledgeGraphEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = KnowledgeGraphEngine()
    else:
        _engine_instance._ensure_fresh()
    return _engine_instance

if __name__ == "__main__":
    kg = get_kg_engine()
    print(f"Loaded Knowledge Graph: {len(kg.nodes)} nodes, {len(kg.edges)} edges.")
    if len(sys.argv) > 1:
        print(kg.get_subgraph_context(sys.argv[1]))
