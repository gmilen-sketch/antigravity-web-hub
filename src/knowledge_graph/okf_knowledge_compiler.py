#!/usr/bin/env python3
"""Open Knowledge Format (OKF v0.2) Knowledge Compiler (`okf_knowledge_compiler.py`).
Implements the public Open Knowledge Format (OKF v0.2) specification
(https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf):
- Compiles high-confidence Knowledge Graph nodes (`okf:*`, `steer:*`, `arch:*`, `skill:*`)
  into structured Markdown dossiers with YAML frontmatter (`okf_version: "0.2"`, `id`, `title`,
  `summary`, `type`, `status`, `confidence`, `last_verified`, `tags`, `aliases`, `related_concepts`, `sources`)
  and `[^source-id]` citation footnotes.
- Synchronizes compiled `kb/` dossiers back into `knowledge_graph.json` and `/dev/shm/kg_warm_cache.json`.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from knowledge_graph.kg_decay_link_predictor import find_active_graph_path
from knowledge_graph.kg_serving_cache import hydrate_serving_cache

DEFAULT_KB_ROOT = os.path.join(REPO_ROOT, "kb")
VALID_TYPES = {"concept", "architecture", "guide", "reference", "troubleshooting", "overview"}
VALID_STATUSES = {"verified", "draft", "deprecated", "experimental"}


def parse_frontmatter(md_text: str) -> Dict[str, Any]:
    """Minimal zero-dependency YAML frontmatter parser for OKF v0.2 Markdown files."""
    if not md_text.startswith("---\n"):
        return {}
    end_idx = md_text.find("\n---\n", 4)
    if end_idx == -1:
        return {}
    raw_yaml = md_text[4:end_idx]
    meta: Dict[str, Any] = {}
    current_list_key = None
    for line in raw_yaml.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - ") and current_list_key:
            val = line[4:].strip().strip('"').strip("'")
            meta.setdefault(current_list_key, []).append(val)
            continue
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if not v:
                current_list_key = k
                meta[k] = []
            elif v.startswith("[") and v.endswith("]"):
                current_list_key = None
                items = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
                meta[k] = items
            else:
                current_list_key = None
                clean_v = v.strip('"').strip("'")
                if clean_v.replace(".", "", 1).isdigit() and k == "confidence":
                    meta[k] = float(clean_v)
                else:
                    meta[k] = clean_v
    return meta


def sync_kb_to_graph(kb_root: str = DEFAULT_KB_ROOT, graph_path: str = None) -> Dict[str, Any]:
    """Reads all OKF v0.2 Markdown dossiers under kb/ and upserts `okf:<id>` nodes into the KG."""
    active_graph = graph_path or find_active_graph_path()
    kb_path = Path(kb_root)
    if not kb_path.exists():
        return {"status": "kb_missing", "kb_root": str(kb_path), "synced_dossiers": 0}

    gdata = {"version": "2.0-OKF-v0.2", "nodes": [], "edges": []}
    if os.path.exists(active_graph) and os.path.getsize(active_graph) > 0:
        try:
            with open(active_graph, "r", encoding="utf-8") as f:
                gdata = json.load(f)
        except Exception:
            pass

    nodes_by_id = {n.get("id"): n for n in gdata.get("nodes", []) if isinstance(n, dict) and n.get("id")}
    edges_set = {
        (e.get("source"), e.get("target"), e.get("relation", "RELATES_TO"))
        for e in gdata.get("edges", [])
        if isinstance(e, dict)
    }

    synced = 0
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    for md_file in sorted(kb_path.rglob("*.md")):
        if md_file.name in ("index.md", "log.md", "README.md"):
            continue
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        meta = parse_frontmatter(text)
        if not meta.get("id"):
            continue
        node_id = f"okf:{meta['id']}"
        body_start = text.find("\n---\n", 4)
        body = text[body_start + 5:].strip() if body_start != -1 else text.strip()
        summary = meta.get("summary") or body.splitlines()[0][:240]
        rel_path = str(md_file.relative_to(kb_path.parent))

        node_obj = {
            "id": node_id,
            "label": meta.get("title", meta["id"]),
            "type": f"OKF_{str(meta.get('type', 'concept')).capitalize()}",
            "description": summary,
            "aliases": meta.get("aliases", []),
            "properties": {
                "okf_version": str(meta.get("okf_version", "0.2")),
                "okf_type": meta.get("type", "concept"),
                "status": meta.get("status", "verified"),
                "confidence": float(meta.get("confidence", 0.98)),
                "last_verified": meta.get("last_verified", now_iso[:10]),
                "kb_path": rel_path,
                "tags": meta.get("tags", []),
            },
            "updated_at": now_iso,
        }
        nodes_by_id[node_id] = node_obj
        synced += 1

        for rel_concept in meta.get("related_concepts", []):
            target_id = rel_concept if ":" in rel_concept else f"okf:{rel_concept}"
            edge_key = (node_id, target_id, "RELATES_TO")
            if edge_key not in edges_set:
                edges_set.add(edge_key)
                gdata.setdefault("edges", []).append({
                    "source": node_id,
                    "target": target_id,
                    "relation": "RELATES_TO",
                    "weight": 0.95,
                })

    gdata["nodes"] = list(nodes_by_id.values())
    os.makedirs(os.path.dirname(active_graph), exist_ok=True)
    with open(active_graph, "w", encoding="utf-8") as f:
        json.dump(gdata, f, indent=2)

    cache_res = hydrate_serving_cache(active_graph)
    return {
        "status": "ok",
        "kb_root": str(kb_path),
        "synced_dossiers": synced,
        "total_graph_nodes": len(gdata["nodes"]),
        "serving_cache": cache_res,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OKF v0.2 Knowledge Compiler")
    parser.add_argument("--kb-root", type=str, default=DEFAULT_KB_ROOT, help="Path to kb/ bundle")
    parser.add_argument("--graph-path", type=str, default=None, help="Path to knowledge_graph.json")
    args = parser.parse_args()
    res = sync_kb_to_graph(kb_root=args.kb_root, graph_path=args.graph_path)
    print(json.dumps(res, indent=2))
