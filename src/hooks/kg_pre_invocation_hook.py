#!/usr/bin/env python3
"""
Clean-Room PreInvocation Grounding Hook for Antigravity Web Hub.
Executes automatically BEFORE every model turn to resolve active entities from
the 0ms POSIX Shared Memory Knowledge Graph cache (/dev/shm/kg_warm_cache.json).
"""

import os
import re
import sys
import json
from typing import Dict, Any, List

KG_CACHE_PATH = "/dev/shm/kg_warm_cache.json"
DEFAULT_KG_JSON = os.path.expanduser(os.environ.get("KG_JSON_PATH", "/mnt/data/knowledge_graph.json"))
FALLBACK_KG_JSON = os.path.expanduser("~/.gemini/antigravity/knowledge_graph.json")

STOP_WORDS = {
    "check", "what", "with", "from", "that", "this", "have", "across", "about",
    "status", "report", "investigate", "audit", "show", "tell", "need", "will",
    "make", "here", "were", "where", "when", "does", "been", "still", "running",
    "please", "help", "also", "come", "next", "step", "again", "they", "them", "their",
}


def load_kg() -> Dict[str, Any]:
    for path in (KG_CACHE_PATH, DEFAULT_KG_JSON, FALLBACK_KG_JSON):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("nodes"):
                return data
        except Exception:
            continue
    return {}


def extract_recent_inputs(transcript_path: str, max_turns: int = 3) -> List[str]:
    if not transcript_path or not os.path.exists(transcript_path):
        return []
    recent = []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if '"USER_INPUT"' in line:
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "USER_INPUT" and obj.get("content"):
                            recent.append(str(obj["content"]))
                    except Exception:
                        pass
    except Exception:
        pass
    return recent[-max_turns:]


def resolve_entities(text: str, kg_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not text or not kg_data:
        return []
    text_lower = text.lower()
    tokens = [t for t in re.findall(r"\b[a-zA-Z0-9_\-/]{3,}\b", text_lower) if t not in STOP_WORDS]
    nodes = kg_data.get("nodes", [])
    scored = []
    for node in nodes:
        nid = str(node.get("id", "")).lower()
        label = str(node.get("label", "")).lower()
        props = node.get("properties", {})
        score = 0
        for t in tokens:
            if t in nid:
                score += 30
            elif t in label:
                score += 20
            else:
                for v in props.values():
                    if isinstance(v, str) and t in v.lower():
                        score += 5
                        break
        if score >= 20:
            clean_props = {
                k: v for k, v in props.items()
                if k not in ("access_history", "raw_payload", "decayed_confidence", "actr_base_activation")
            }
            scored.append((score, {
                "id": node.get("id"),
                "label": node.get("label", node.get("id")),
                "type": node.get("type", "entity"),
                "properties": clean_props,
            }))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:4]]


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    transcript_path = payload.get("transcriptPath", "")
    recent_inputs = extract_recent_inputs(transcript_path, max_turns=3)
    context_text = " \n ".join(recent_inputs) if recent_inputs else ""

    kg_data = load_kg()
    matched = resolve_entities(context_text, kg_data)

    if matched:
        lines = [
            "🧠 [KNOWLEDGE GRAPH PRE-INVOCATION GROUNDING (SSOT)]",
            "- Knowledge Graph properties are authoritative and pre-loaded from /dev/shm RAM cache.",
        ]
        for e in matched:
            lines.append(f"- Entity: `{e['id']}` ({e['label']}) [{e['type']}]")
            for k, v in e["properties"].items():
                if isinstance(v, (str, int, float, bool)):
                    lines.append(f"  * {k}: {v}")
        output = {"injectSteps": [{"ephemeralMessage": "\n".join(lines)}]}
    else:
        output = {"injectSteps": []}

    print(json.dumps(output))


if __name__ == "__main__":
    main()
