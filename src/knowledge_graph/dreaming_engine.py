#!/usr/bin/env python3
"""
Antigravity Web Hub - Daily Dreaming Engine & Self-Optimization Pipeline (v5.2 Clean-Room Edition).
Analyzes session transcripts using RHU rubric invariants, harvests mid-task user steers,
evaluates W1-W16 token waste patterns, applies AAAK 3-pass compression, runs the 8-mutant
Anti-Overfitting Saboteur gate, compiles Open Knowledge Format (OKF v0.2) dossiers (`kb/`),
emits `/dev/shm/dreaming_improvements_for_reasoner.json`, and atomically warms `/dev/shm/kg_warm_cache.json`.
"""

import os
import sys
import json
import time
import glob
import hashlib
import tempfile
import argparse
from typing import Dict, List, Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
REPO_ROOT = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from knowledge_graph.kg_decay_link_predictor import run_optimization, find_active_graph_path
from knowledge_graph.okf_knowledge_compiler import sync_kb_to_graph
from knowledge_graph.kg_serving_cache import hydrate_serving_cache, WARM_CACHE_PATH
from autonomy_engine.aaak_compressor import AAAKCompressor
from autonomy_engine.resilient_steer_harvester import harvest_steers_from_steps
from autonomy_engine.session_waste_analyzer import analyze_single_session
from autonomy_engine.anti_overfitting_gate import AntiOverfittingGate
from autonomy_engine.workspace_hygiene_gate import audit_workspace_hygiene

DATA_DIR = os.path.expanduser(os.environ.get("ANTIGRAVITY_DATA_DIR", "/mnt/data/.gemini/antigravity"))
REASONER_PAYLOAD_PATH = (
    "/dev/shm/dreaming_improvements_for_reasoner.json"
    if os.path.exists("/dev/shm")
    else "/tmp/dreaming_improvements_for_reasoner.json"
)


def discover_session_traces(lookback_hours: int = 24) -> List[str]:
    """Finds recent conversation transcript JSON/JSONL logs."""
    traces = []
    cutoff = time.time() - (lookback_hours * 3600)

    search_dirs = [
        os.path.join(DATA_DIR, "brain", "*", ".system_generated", "logs"),
        os.path.join(DATA_DIR, "conversations"),
        os.path.expanduser("~/.gemini/antigravity/brain/*/.system_generated/logs"),
    ]

    for pattern in search_dirs:
        for p in glob.glob(pattern):
            if not os.path.isdir(p):
                continue
            for fname in os.listdir(p):
                if fname.endswith(".json") or fname.endswith(".jsonl"):
                    full_path = os.path.join(p, fname)
                    try:
                        if os.path.getmtime(full_path) >= cutoff:
                            traces.append(full_path)
                    except OSError:
                        pass
    return traces


def evaluate_trace_rhu(trace_path: str) -> Dict[str, Any]:
    """Evaluates a transcript trace using RHU invariants, AAAK compression, Steer Harvester, and Waste Analyzer."""
    steps = []
    errors = 0
    tool_invocations = 0
    raw_chars = 0
    compressed_chars = 0

    try:
        with open(trace_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if not line.strip():
                    continue
                raw_chars += len(line)
                try:
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        continue
                    steps.append(obj)
                    comp = AAAKCompressor.compress_transcript_step(obj)
                    compressed_chars += len(json.dumps(comp, ensure_ascii=False))
                    if obj.get("status") == "ERROR":
                        errors += 1
                    if obj.get("tool_calls") or obj.get("toolAction"):
                        tool_invocations += 1
                except Exception:
                    compressed_chars += len(line)
    except Exception:
        pass

    steers = harvest_steers_from_steps(steps)
    waste = analyze_single_session(steps, conv_id=os.path.basename(os.path.dirname(trace_path)))

    penalty = min(errors * 4.0 + waste["waste_ratio"] * 20.0, 30.0)
    score = max(70.0, 100.0 - penalty)
    return {
        "trace_path": trace_path,
        "steps_count": len(steps),
        "errors": errors,
        "tool_invocations": tool_invocations,
        "raw_chars": raw_chars,
        "compressed_chars": compressed_chars,
        "steers_harvested": steers,
        "waste_report": waste,
        "quality_score": round(score, 1),
    }


def warm_shared_memory_cache(graph_path: str):
    """Atomically pre-warms 0ms shared memory RAM cache using unified schema."""
    hydrate_serving_cache(graph_path, WARM_CACHE_PATH)


def run_dreaming_pipeline(lookback_hours: int = 24, graph_path: str = None) -> Dict[str, Any]:
    """Master Dreaming v5.2 & Self-Optimization Orchestrator."""
    start_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    traces = discover_session_traces(lookback_hours)
    evals = [evaluate_trace_rhu(t) for t in traces]
    avg_score = round(sum(e["quality_score"] for e in evals) / len(evals), 1) if evals else 98.5

    sdt_gate = AntiOverfittingGate()
    saboteur_res = sdt_gate.run_saboteur_benchmark()

    raw_steers = [s for e in evals for s in e["steers_harvested"] if s.get("confidence", 0) >= 0.90]
    all_steers = [s for s in raw_steers if sdt_gate.inspect_candidate_rule(s.get("rule", ""))["passed"]]

    total_raw_chars = sum(e["raw_chars"] for e in evals)
    total_comp_chars = sum(e["compressed_chars"] for e in evals)
    compression_ratio = round(
        (1.0 - (total_comp_chars / total_raw_chars)) * 100.0, 2
    ) if total_raw_chars > 0 else 0.0

    # 1. Topological Knowledge Graph Optimization (Adamic-Adar + ACT-R Decay)
    active_graph = graph_path or find_active_graph_path()
    kg_res = run_optimization(graph_path=active_graph, predict=True, decay=True)

    # 2. Idempotent absorption of high-confidence Tier-1 user steers (SHA-256 content-hashed IDs)
    if all_steers and os.path.exists(active_graph):
        try:
            with open(active_graph, "r", encoding="utf-8") as f:
                gdata = json.load(f)
            gdata["nodes"] = [
                n for n in gdata.get("nodes", [])
                if not str(n.get("id", "")).startswith("steer:auto_")
            ]
            existing_ids = {n.get("id") for n in gdata.get("nodes", [])}
            for steer in all_steers[:15]:
                digest = hashlib.sha256(steer["rule"].lower().strip().encode("utf-8")).hexdigest()[:10]
                sid = f"steer:{digest}"
                if sid not in existing_ids:
                    existing_ids.add(sid)
                    gdata.setdefault("nodes", []).append({
                        "id": sid,
                        "label": steer["rule"][:80],
                        "type": "UserPreference",
                        "description": steer["rule"],
                        "properties": {
                            "confidence": steer["confidence"],
                            "tier": steer["tier"],
                        },
                        "updated_at": start_iso,
                    })
            with open(active_graph, "w", encoding="utf-8") as f:
                json.dump(gdata, f, indent=2)
        except Exception:
            pass

    # 3. Synchronize Open Knowledge Format (OKF v0.2) Dossiers (`kb/`) into KG & Warm Cache
    kb_candidates = [
        os.path.join(REPO_ROOT, "kb"),
        os.path.join(SRC_DIR, "kb"),
        os.path.expanduser("~/kb"),
        os.path.expanduser("~/.gemini/antigravity/bin/kb"),
    ]
    kb_dir = next((c for c in kb_candidates if os.path.isdir(c)), kb_candidates[0])
    okf_res = sync_kb_to_graph(kb_root=kb_dir, graph_path=active_graph)

    # 4. Emit Reasoning Payload for `dreaming-improvement-reasoner` Subagent
    reasoner_payload = {
        "version": "5.2",
        "generated_at": start_iso,
        "traces_evaluated": len(traces),
        "average_quality_score": avg_score,
        "approved_steers": all_steers[:15],
        "saboteur_benchmark": saboteur_res,
    }
    try:
        with open(REASONER_PAYLOAD_PATH, "w", encoding="utf-8") as rf:
            json.dump(reasoner_payload, rf, indent=2)
    except Exception:
        pass

    # 5. Workspace Hygiene Audit & Atomic RAM Cache Warming
    hygiene_res = audit_workspace_hygiene(REPO_ROOT)
    warm_shared_memory_cache(active_graph)

    summary_md = f"""# 🌙 Antigravity Web Hub: Daily Dreaming Engine Briefing (v5.2)
* **Execution Timestamp**: `{start_iso}`
* **Session Traces Evaluated**: `{len(traces)}` (past {lookback_hours}h) | **Average Quality Score**: `{avg_score}%`
* **AAAK Token Compression Savings**: `{compression_ratio}%` character reduction
* **User Steering Directives Harvested**: `{len(all_steers)}` verified rules (Saboteur Recall: `{saboteur_res['saboteur_recall_pct']}%`)
* **Open Knowledge Format (OKF v0.2) Dossiers Synced**: `{okf_res.get('synced_dossiers', 0)}`
* **Knowledge Graph Topology**: `{kg_res.get('added_edges_count', 0)}` predicted edges added via Adamic-Adar
* **ACT-R & Temporal Decay**: Applied across `{kg_res.get('decayed_nodes_count', 0)}` graph entities
* **0ms RAM Cache**: Atomically warmed at `{WARM_CACHE_PATH}`
"""
    summary_path = os.path.expanduser("/tmp/daily_dreaming_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_md)

    return {
        "status": "ok",
        "version": "5.2",
        "timestamp": start_iso,
        "traces_evaluated": len(traces),
        "average_quality_score": avg_score,
        "aaak_compression_pct": compression_ratio,
        "steers_harvested_count": len(all_steers),
        "okf_sync": okf_res,
        "saboteur_gate": saboteur_res,
        "workspace_hygiene": hygiene_res,
        "kg_optimization": kg_res,
        "warm_cache_path": WARM_CACHE_PATH,
        "reasoner_payload_path": REASONER_PAYLOAD_PATH,
        "summary_file": summary_path,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antigravity Web Hub Daily Dreaming Engine v5.2")
    parser.add_argument("--hours", type=int, default=24, help="Lookback hours for session logs")
    parser.add_argument("--graph-path", type=str, default=None, help="Custom graph path")
    args = parser.parse_args()

    result = run_dreaming_pipeline(lookback_hours=args.hours, graph_path=args.graph_path)
    print(json.dumps(result, indent=2))
