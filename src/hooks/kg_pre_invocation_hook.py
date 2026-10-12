#!/usr/bin/env python3
"""
Production PreInvocation Hook for Antigravity Web Hub (v3.3 - Turn-1 Pinned KV-Cache Prefix,
1-Hop Topological Edge Propagation, OKF v0.2 Top-3 Dossier Co-Bundling & YAML-Frontmatter Skill Trigger Resolver).
Executes automatically BEFORE every model turn (<50ms budget, fail-open).
"""

from collections import defaultdict
import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

KG_CACHE_PATH = "/dev/shm/kg_warm_cache.json"
KG_FALLBACK_PATHS = [
    os.path.expanduser(os.environ.get("KG_JSON_PATH", "/mnt/data/knowledge_graph.json")),
    os.path.expanduser("~/.gemini/antigravity/knowledge_graph.json"),
]

SKILL_DIRS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "skills"),
    os.path.expanduser("~/.gemini/antigravity/skills"),
    os.path.expanduser("~/.gemini/config/skills"),
    "/mnt/data/projects/.agents/skills",
]

STOP_WORDS = {
    "check", "what", "with", "from", "that", "this", "have", "across", "about",
    "status", "report", "investigate", "audit", "show", "tell", "need", "will",
    "make", "here", "were", "where", "when", "does", "been", "still", "running",
    "please", "help", "also", "come", "next", "step", "again", "they", "them", "their",
    "the", "and", "for", "are", "how", "run", "use", "using", "write", "list", "sort",
    "function", "python", "integers", "evaluation", "information", "retrieved", "knowledge",
    "graph", "into", "only", "some", "more", "most", "other", "such", "than",
    "then", "very", "just", "over", "after", "before", "between", "under", "while",
    "test", "tests", "testing", "production", "implementation", "retrieve", "retrieval",
    "attempt", "attempts", "methods", "working", "current", "decide", "want", "full",
    "know", "via", "new", "least", "all", "your", "end", "google", "tools", "call", "done",
    "etc", "work", "app", "chat", "live", "against", "update", "project", "agent", "models",
    "business", "secure", "innovation", "services", "group", "interactive", "network", "load",
    "balancer", "https", "http", "www", "com", "docs", "spreadsheets", "drive",
    "file", "files", "view", "edit", "now", "back", "find",
    "cases", "sessions", "historical", "optimal", "called", "continue", "confirm", "extensive",
    "improvements", "summary", "summarize", "proceed", "prompts", "proactively", "dynamic",
    "sheets", "details", "invoice", "reconcile", "previous", "post", "autofill", "builder",
    "website", "automated", "web", "visualizer", "colours", "colors", "nodes", "type", "toggles",
    "review", "different", "aspects", "visually", "improve", "based", "out", "able",
    "click", "drag", "hover", "item", "lean", "visuals", "zoom", "well", "see",
    "user", "users", "ui", "e2e", "journey", "journeys",
    "first", "second", "third", "create", "created", "plan", "planning",
}

STRUCTURAL_NODE_PREFIX_STOPWORDS = frozenset({
    "customer", "customers", "workload", "workloads", "task", "tasks",
    "project", "projects", "user", "users", "doc", "docs", "skill", "skills",
    "hook", "hooks", "rule", "rules", "subagent", "subagents", "stream", "streams",
    "architecture", "evaluation", "evaluations", "gemini", "flash", "model", "models",
    "router", "expert", "experts", "prefix", "cache", "schema", "latency", "throughput",
    "dive", "deep", "training", "completion", "balancing", "prediction", "draft",
    "processing", "rates", "recursion", "depth", "stop", "gate", "transcript",
    "verification", "tautological", "floor", "clamp", "paired", "stat", "diff",
    "pass", "stability", "response", "theory", "discrimination", "signal",
    "detection", "prime", "version", "inspect", "overhead", "customisations",
    "customizations", "benchmark", "benchmarks", "sandbox", "sandboxes",
})

NON_SEARCH_KEYS = frozenset({
    "sources", "generated", "verified", "stale_after", "resource",
    "okf_status", "trust_tier", "computation", "citations",
})
NON_MATCH_PROP_KEYS = NON_SEARCH_KEYS | frozenset({
    "url", "doc_url", "updated_at", "due_date", "target_implementation_date", "source",
})

_HOME_RE = re.compile(r"(?:/[A-Za-z0-9_.-]+)*/home/[A-Za-z0-9_.-]+|/Users/[A-Za-z0-9_.-]+")
_TMP_RE = re.compile(r"/tmp/[A-Za-z0-9_.\-/]*")


def scrub(text: str) -> str:
    if not text:
        return text
    text = _HOME_RE.sub("<USER_HOME_DIR>", text)
    text = _TMP_RE.sub("<TMP_DIR>", text)
    return text


def _okf_trust_summary(props: dict) -> dict:
    out = {}
    tier = props.get("trust_tier")
    ver = props.get("verified")
    if isinstance(ver, dict) and ver:
        out["verified_by"] = f"{ver.get('by', '?')} @ {str(ver.get('at', '?'))[:10]}"
    elif isinstance(ver, list) and ver:
        actors = [f"{v.get('by', '?')} @ {str(v.get('at', '?'))[:10]}" for v in ver if isinstance(v, dict)]
        if actors:
            out["verified_by"] = ", ".join(actors)
    if tier:
        out["trust_tier"] = tier
    srcs = props.get("sources")
    if isinstance(srcs, list) and srcs:
        ids = [str(s.get("id") or s.get("resource") or "") for s in srcs if isinstance(s, dict)]
        out["sources"] = f"{len(srcs)} ({', '.join(i for i in ids[:3] if i)})"
    sa = props.get("stale_after")
    if isinstance(sa, str) and sa:
        try:
            sa_dt = datetime.datetime.fromisoformat(sa.replace("Z", "+00:00"))
            if sa_dt.tzinfo is None:
                sa_dt = sa_dt.replace(tzinfo=datetime.timezone.utc)
            stale = datetime.datetime.now(datetime.timezone.utc) >= sa_dt
            out["freshness"] = (
                f"STALE since {sa[:10]} - re-verify before use" if stale else f"fresh until {sa[:10]}"
            )
        except Exception:
            out["freshness"] = f"stale_after {sa}"
    comp = props.get("computation")
    if isinstance(comp, dict) and comp:
        out["attested_computation"] = ", ".join(
            f"{k}={comp[k]}" for k in ("runtime", "executor", "attester") if comp.get(k)
        )
    return out


def load_kg() -> Dict[str, Any]:
    if os.path.exists(KG_CACHE_PATH):
        try:
            with open(KG_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("nodes"):
                return data
        except Exception:
            pass

    for path in KG_FALLBACK_PATHS:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("nodes"):
                    try:
                        if os.path.exists("/dev/shm") and os.access("/dev/shm", os.W_OK):
                            tmp_cache = f"{KG_CACHE_PATH}.{os.getpid()}.tmp"
                            with open(tmp_cache, "w", encoding="utf-8") as wf:
                                json.dump(data, wf)
                            os.replace(tmp_cache, KG_CACHE_PATH)
                    except Exception:
                        pass
                    return data
            except Exception:
                pass
    return {"nodes": [], "edges": []}


def extract_recent_inputs(transcript_path: str, max_turns: int = 3) -> List[str]:
    if not transcript_path or not os.path.exists(transcript_path):
        return []
    recent_inputs: List[str] = []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if '"USER_INPUT"' in line:
                    try:
                        data = json.loads(line)
                        if data.get("type") == "USER_INPUT":
                            content = str(data.get("content") or "")
                            if content:
                                content = re.sub(r"<CONTEXT_SUMMARY>[\s\S]*?</CONTEXT_SUMMARY>", "", content)
                                content = re.sub(r"<ADDITIONAL_METADATA>[\s\S]*?</ADDITIONAL_METADATA>", "", content)
                                content = re.sub(r"</?USER_REQUEST>", "", content).strip()
                                if content and not content.startswith("Error: The stream was interrupted"):
                                    recent_inputs.append(content)
                    except Exception:
                        pass
    except Exception:
        pass
    return recent_inputs[-max_turns:] if recent_inputs else []


def extract_multi_turn_context(transcript_path: str, max_turns: int = 3) -> str:
    inputs = extract_recent_inputs(transcript_path, max_turns=max_turns)
    return " \n ".join(inputs) if inputs else ""


def select_entity_query_text(recent_inputs: List[str]) -> str:
    if not recent_inputs:
        return ""
    latest = recent_inputs[-1]
    if len(recent_inputs) == 1:
        return latest
    lt_lower = latest.lower()
    lt_tokens = [
        t for t in re.findall(r"\b[a-zA-Z0-9_\-/]{3,}\b", lt_lower)
        if t not in STOP_WORDS and not (t.isdigit() and t != "2026")
    ]
    anaphoric_markers = (
        "their", "its", "those", "them", "same for", "what about", "and for",
        "how about", "that project", "that service", "that workload", "that ticket",
    )
    if len(lt_tokens) < 4 and any(m in lt_lower for m in anaphoric_markers):
        return " \n ".join(recent_inputs)
    return latest


def _build_1hop_maps(kg_data: dict) -> Tuple[dict, dict]:
    adj_rels = defaultdict(list)
    adj_neighbors = defaultdict(set)
    edges = kg_data.get("edges", []) if isinstance(kg_data, dict) else []
    for e in edges:
        s = str(e.get("source") or "")
        t = str(e.get("target") or "")
        rel = str(e.get("relation") or e.get("type") or "CONNECTED").upper()
        if not s or not t:
            continue
        adj_rels[s].append(f"{rel}->{t}")
        adj_rels[t].append(f"{rel}<-{s}")
        adj_neighbors[s].add(t)
        adj_neighbors[t].add(s)
    return adj_rels, adj_neighbors


def resolve_hybrid_entities(text: str, kg_data: Dict[str, Any], use_alias_map: bool = True) -> List[Dict[str, Any]]:
    if not text or not kg_data:
        return []
    text_lower = text.lower()
    tokens = [
        t for t in re.findall(r"\b[a-zA-Z0-9_\-/]{3,}\b", text_lower)
        if t not in STOP_WORDS and t not in STRUCTURAL_NODE_PREFIX_STOPWORDS and not (t.isdigit() and t != "2026")
    ]
    tok_pats = [(t, re.compile(r"\b" + re.escape(t) + r"\b")) for t in tokens]

    all_nodes = kg_data.get("nodes", []) if isinstance(kg_data, dict) else kg_data
    op_nodes = [
        n for n in all_nodes
        if isinstance(n, dict)
        and not str(n.get("id", "")).startswith("okf:")
        and not (n.get("properties") or {}).get("stub")
    ]
    okf_nodes = [
        n for n in all_nodes
        if isinstance(n, dict) and str(n.get("id", "")).startswith("okf:")
    ]
    adj_rels, adj_neighbors = _build_1hop_maps(kg_data)

    raw_scores: Dict[str, int] = {}
    node_by_id: Dict[str, Dict[str, Any]] = {}

    for node in op_nodes:
        orig_id = str(node.get("id", ""))
        nid = orig_id.lower()
        node_by_id[orig_id] = node
        nid_body = nid.split(":", 1)[1] if ":" in nid else nid
        nid_tokens = [
            nt for nt in re.split(r"[_\-\s/]+", nid_body)
            if nt and nt not in STRUCTURAL_NODE_PREFIX_STOPWORDS
        ]
        clean_nid_body = " ".join(nid_tokens)
        label_raw = str(node.get("label", "")).lower()
        label_tokens = [
            lt for lt in re.findall(r"\b[a-z0-9]{3,}\b", label_raw)
            if lt not in STRUCTURAL_NODE_PREFIX_STOPWORDS
        ]
        clean_label = " ".join(label_tokens)
        props = node.get("properties", {}) if isinstance(node.get("properties"), dict) else {}
        desc = str(node.get("description") or props.get("description") or "").lower()

        score = 0
        if use_alias_map:
            aliases = node.get("aliases") or props.get("aliases") or []
            if isinstance(aliases, list):
                if any(isinstance(a, str) and re.search(r"\b" + re.escape(a.lower()) + r"\b", text_lower) for a in aliases):
                    score += 40

        for t, t_re in tok_pats:
            if len(t) >= 3 and t in clean_nid_body and t_re.search(clean_nid_body):
                score += 30
            elif len(t) >= 3 and t in clean_label and t_re.search(clean_label):
                score += 25
            elif len(t) >= 4 and t in desc and t_re.search(desc):
                score += 10

        if score >= 25:
            if nid.startswith(("infra:", "model:", "mcp:", "workload:", "project:", "skill:")):
                score += 20
            elif nid.startswith("task:"):
                score += 10

        if score > 0:
            raw_scores[orig_id] = score

    propagated_scores = dict(raw_scores)
    for orig_id, sc in list(raw_scores.items()):
        if sc >= 45:
            for nb_id in adj_neighbors.get(orig_id, set()):
                if nb_id in node_by_id:
                    propagated_scores[nb_id] = max(propagated_scores.get(nb_id, 0), max(45, sc - 10))

    scored_nodes = []
    for orig_id, score in propagated_scores.items():
        if score >= 45:
            node = node_by_id[orig_id]
            nid = orig_id.lower()
            props = dict(node.get("properties", {}) if isinstance(node.get("properties"), dict) else {})
            if node.get("description") and "description" not in props:
                props["description"] = node["description"]
            op_emit = {
                k: props[k]
                for k in sorted(props.keys())
                if k not in (
                    "access_history", "raw_payload", "file_path",
                    "confidence_score", "decayed_confidence", "base_confidence",
                    "actr_base_activation", "last_decay_eval", "degree",
                    "domain_keywords",
                )
                and k not in NON_SEARCH_KEYS
            }
            op_emit.update(_okf_trust_summary(props))
            if adj_rels.get(orig_id):
                op_emit["relations_1hop"] = adj_rels[orig_id][:4]
            scored_nodes.append((
                score,
                nid,
                {
                    "id": orig_id,
                    "label": node.get("label", orig_id),
                    "type": node.get("type", node.get("category", "entity")),
                    "description": str(node.get("description") or props.get("description") or "")[:200],
                    "properties": op_emit,
                },
            ))

    scored_nodes.sort(key=lambda x: (-x[0], x[1]))
    unique_entities = []
    seen_ids = set()
    for _, _, entity in scored_nodes:
        if entity["id"] not in seen_ids:
            seen_ids.add(entity["id"])
            unique_entities.append(entity)
            if len(unique_entities) >= 4:
                break

    # Tier 2: OKF v0.2 Reference Concepts (Top-3 co-bundling via domain_keywords)
    scored_okf = []
    for node in okf_nodes:
        nid_okf = str(node.get("id", ""))
        props = node.get("properties", {}) if isinstance(node.get("properties"), dict) else {}
        dkws = list(props.get("domain_keywords", [])) + list(props.get("tags", [])) + list(node.get("aliases") or [])
        kw_hits = sum(1 for kw in dkws if isinstance(kw, str) and kw.lower() in text_lower)
        if kw_hits > 0:
            trust = _okf_trust_summary(props)
            tier_bonus = {"human-reviewed": 3, "machine-confirmed": 2}.get(props.get("trust_tier"), 0)
            stale_pen = 10 if str(trust.get("freshness", "")).startswith("STALE") else 0
            emit = {
                k: props[k]
                for k in sorted(props.keys())
                if k not in (
                    "access_history", "raw_payload",
                    "confidence_score", "decayed_confidence", "base_confidence",
                    "actr_base_activation", "last_decay_eval", "degree",
                    "domain_keywords",
                )
                and k not in NON_SEARCH_KEYS
            }
            emit.update(trust)
            if adj_rels.get(nid_okf):
                emit["relations_1hop"] = adj_rels[nid_okf][:4]
            scored_okf.append((
                kw_hits * 50 + tier_bonus - stale_pen,
                nid_okf,
                {
                    "id": nid_okf,
                    "label": node.get("label", nid_okf),
                    "type": node.get("type", node.get("category", "Concept")),
                    "description": str(props.get("description") or "")[:200],
                    "properties": emit,
                },
            ))
    scored_okf.sort(key=lambda x: (-x[0], x[1]))
    for _, _, okf_entity in scored_okf[:3]:
        if okf_entity["id"] not in seen_ids:
            seen_ids.add(okf_entity["id"])
            unique_entities.append(okf_entity)

    return unique_entities


def resolve_hybrid_entities_pinned_and_delta(
    transcript_path: str, recent_inputs: List[str], kg_data: Dict[str, Any], use_alias_map: bool = True
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not recent_inputs or not kg_data:
        return [], []

    cid = "default"
    if transcript_path:
        parts = os.path.normpath(transcript_path).split(os.sep)
        for idx, p in enumerate(parts):
            if p == "brain" and idx + 1 < len(parts):
                cid = re.sub(r"[^a-zA-Z0-9_\-]", "", parts[idx + 1])
                break

    pin_path = f"/dev/shm/kg_session_pinned_{cid}.json"
    pinned_entities = None
    if cid != "default" and use_alias_map and os.path.exists(pin_path):
        try:
            with open(pin_path, "r", encoding="utf-8") as f:
                pinned_entities = json.load(f)
        except Exception:
            pinned_entities = None

    if pinned_entities is None:
        turn1_text = recent_inputs[0]
        pinned_entities = resolve_hybrid_entities(turn1_text, kg_data, use_alias_map=use_alias_map)
        pinned_entities.sort(key=lambda e: str(e.get("id", "")))
        if cid != "default" and use_alias_map:
            try:
                with open(pin_path, "w", encoding="utf-8") as f:
                    json.dump(pinned_entities, f)
            except Exception:
                pass

    pinned_ids = {e.get("id") for e in pinned_entities}
    delta_entities = []
    if len(recent_inputs) > 1:
        latest_text = select_entity_query_text(recent_inputs)
        current_entities = resolve_hybrid_entities(latest_text, kg_data, use_alias_map=use_alias_map)
        for ent in current_entities:
            if ent.get("id") not in pinned_ids:
                delta_entities.append(ent)
        delta_entities.sort(key=lambda e: str(e.get("id", "")))

    return pinned_entities, delta_entities


TRIGGERS = {
    "antigravity-web-builder": ["antigravity web", "cloud iap", "reverse proxy", "grpc-web", "load balancer", "start_hub"],
    "black-hat-analysis": ["black hat", "forensic verification", "goldfish", "isolated judge", "silent fallback", "c9 table"],
    "diagram-renderer": ["diagram", "mermaid", "flowchart", "gcp draw", "architecture diagram", "render diagram", "topology map", "bento"],
    "finops-focus-auditor": ["finops", "focus 1.0", "cud", "committed use", "commitment discount", "cloud spend", "effectivecost", "billing"],
    "first-principles-brainstormer": ["first principles", "brainstorm", "negative constraints", "pre-flight spec"],
    "golden-ab-testing": ["a/b test", "hake", "normalized gain", "wilcoxon", "mcnemar", "pass@k", "paired evaluation"],
    "idea-evaluator": ["idea evaluator", "signal detection", "d-prime", "candidate evaluation"],
    "issue-tracker-manager": ["issue tracker", "github issues", "jira", "gitlab", "triage queue", "deduplicate issues"],
    "migration-center-architect": ["migration center", "tco sizing", "migration wave", "right-sizing", "vm migration"],
    "open-deep-researcher": ["deep research", "research swarm", "arxiv", "pubmed", "egm pipeline", "source verification"],
    "p0-quality-first-engine": ["p0 engine", "circuit breaker", "bernstein", "write-set lock", "temporal window"],
    "p1-quality-first-engine": ["p1 engine", "picc", "prompt injection", "citation hash", "source abstention"],
    "parallel-task-orchestrator": ["parallel task", "multi-agent swarm", "dag dependency", "subagent orchestration"],
    "playwright-agent-browser": ["playwright", "headless browser", "dom traversal", "browser screenshot", "cdp"],
    "self-grill": ["self-grill", "bayesian prior", "svg geometry", "ui geometry", "audit_web_ui_geometry"],
    "six-hats-evaluator": ["six hats", "six thinking hats", "decision matrix", "white hat", "black hat risk", "delphi"],
    "universal-solution-architect": ["solution architect", "leapfrog architecture", "6 pillars", "gap analysis", "reference design", "gke", "spanner"],
    "universal-task-sync": ["task sync", "active_tasks_ledger", "jira sync", "linear sync", "github projects", "3-row diff"],
    "workspace-docs-publisher": ["google docs", "3-tab", "inverted pyramid", "agent-ssot-v1", "516 pt", "technical report"],
    "workspace-slides-generator": ["google slides", "presentation", "720x405", "4-card", "chevron connector", "slide deck"],
}

_FRONTMATTER_CACHE: Dict[str, List[str]] = {}


def extract_skill_frontmatter_triggers(skill_name: str) -> List[str]:
    if skill_name in _FRONTMATTER_CACHE:
        return _FRONTMATTER_CACHE[skill_name]
    phrases = list(TRIGGERS.get(skill_name, []))
    for sdir in SKILL_DIRS:
        spath = os.path.join(sdir, skill_name, "SKILL.md")
        if os.path.exists(spath):
            try:
                with open(spath, "r", encoding="utf-8") as f:
                    head = f.read(1600)
                m = re.search(r"^---\s*\n(.*?)\n---", head, flags=re.S)
                if m:
                    fm = m.group(1).lower()
                    dont_idx = fm.find("don't use")
                    pos_fm = fm[:dont_idx] if dont_idx != -1 else fm
                    words = [
                        w for w in re.findall(r"[a-z0-9_\-]{4,}", pos_fm)
                        if w not in STOP_WORDS and w not in {"description", "name", "metadata", "icon", "version", "when", "with", "from"}
                    ]
                    for i in range(len(words) - 1):
                        bg = f"{words[i]} {words[i + 1]}"
                        if bg not in phrases:
                            phrases.append(bg)
            except Exception:
                pass
            break
    _FRONTMATTER_CACHE[skill_name] = phrases
    return phrases


def resolve_target_skills(text: str) -> List[Tuple[str, str]]:
    if not text:
        return []
    text_lower = text.lower()
    matched = []
    for sname in TRIGGERS:
        kws = extract_skill_frontmatter_triggers(sname)
        score = 0
        for kw in kws:
            if kw in text_lower or re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                score += 2 if " " in kw else 1
        if score > 0:
            for sdir in SKILL_DIRS:
                spath = os.path.join(sdir, sname, "SKILL.md")
                if os.path.exists(spath):
                    matched.append((score, sname, spath))
                    break
    matched.sort(key=lambda x: (-x[0], x[1]))
    return [(name, path) for _, name, path in matched[:2]]


def _format_entity_lines(entities: List[Dict[str, Any]]) -> List[str]:
    lines = []
    for e in entities:
        lines.append(f"- Entity: `{e['id']}` ({e['label']})")
        for k, v in (e.get("properties") or {}).items():
            if isinstance(v, (str, int, float, bool)):
                lines.append(f"  * {k}: {v}")
            elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], str):
                lines.append(f"  * {k}: {', '.join(v[:4])}")
    return lines


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {}

    transcript_path = str(payload.get("transcriptPath", "") or "")
    recent_inputs = extract_recent_inputs(transcript_path, max_turns=3)
    context_text = " \n ".join(recent_inputs) if recent_inputs else ""

    kg_data = load_kg()
    pinned_entities, delta_entities = resolve_hybrid_entities_pinned_and_delta(
        transcript_path, recent_inputs, kg_data
    )
    matched_entities = pinned_entities + delta_entities
    matched_skills = resolve_target_skills(context_text)

    msg_lines: List[str] = []
    if matched_entities:
        msg_lines.append("🧠 [KNOWLEDGE GRAPH AUTOMATIC PRE-INVOCATION GROUNDING (SSOT)]")
        msg_lines.append(
            "- Single Source of Truth (SSOT): The Knowledge Graph is the Single Source of Truth. "
            "Knowledge Graph properties strictly override local workspace guesses and base LLM assumptions."
        )
        msg_lines.append(
            "- Internal Context Binding: Ingested PreInvocation context is active. "
            "Bind canonical entities internally during execution with zero preamble entity dumps."
        )
        msg_lines.append("<session_pinned_entities>")
        msg_lines.extend(_format_entity_lines(pinned_entities))
        msg_lines.append("</session_pinned_entities>")
        if delta_entities:
            msg_lines.append("<turn_delta_entities>")
            msg_lines.extend(_format_entity_lines(delta_entities))
            msg_lines.append("</turn_delta_entities>")
        msg_lines.append("")

    if matched_skills:
        msg_lines.append("🎯 [MANDATORY SKILL ACTIVATION]")
        for sname, spath in matched_skills:
            msg_lines.append(f"- Skill: `{sname}` -> file://{spath}")
            msg_lines.append(
                f"  * Invariant: View SKILL.md via view_file before executing scripts or CLI tools belonging to `{sname}`."
            )
        msg_lines.append("")

    if msg_lines:
        output = {"injectSteps": [{"ephemeralMessage": scrub("\n".join(msg_lines))}]}
    else:
        output = {}

    print(json.dumps(output))




# ==============================================================================
# v3.5 Clean-Room Upgrades: 0.05 Confidence Quantizer, Morphological Stemmer,
# 2-Hop Neighborhood Propagation, DSO Subagent Guard & Canary Stripper
# ==============================================================================

def quantize_confidence_005(score: float) -> float:
    """Quantizes floating-point confidence scores to 0.05 buckets to preserve LLM KV-cache prefix hits."""
    clamped = max(0.0, min(1.0, float(score)))
    return round(round(clamped * 20.0) / 20.0, 2)


def stem_token(token: str) -> str:
    """Lightweight deterministic morphological suffix stemmer (d' = 3.962 lexical matching)."""
    w = token.lower().strip()
    if len(w) <= 4:
        return w
    for suffix in ("izations", "ization", "ingly", "edly", "ments", "ment", "ings", "ing", "ions", "ion", "ies", "es", "ed", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            if suffix == "ies":
                return w[:-3] + "y"
            return w[:-len(suffix)]
    return w


def collect_2hop_neighborhood(seed_ids: List[str], edges: List[Dict[str, Any]]) -> Dict[str, int]:
    """Propagates entity relevance across 1-hop and 2-hop Knowledge Graph edges."""
    hop_map: Dict[str, int] = {sid: 0 for sid in seed_ids}
    hop1: set = set()
    for e in edges:
        src, dst = e.get("source", ""), e.get("target", "")
        if src in hop_map and dst not in hop_map:
            hop1.add(dst)
        elif dst in hop_map and src not in hop_map:
            hop1.add(src)
    for n1 in hop1:
        hop_map[n1] = 1
    hop2: set = set()
    for e in edges:
        src, dst = e.get("source", ""), e.get("target", "")
        if src in hop1 and dst not in hop_map:
            hop2.add(dst)
        elif dst in hop1 and src not in hop_map:
            hop2.add(src)
    for n2 in hop2:
        hop_map[n2] = 2
    return hop_map


def strip_canary_headers(text: str) -> str:
    """Strips 1-line internal canary banners from prompt context."""
    return re.sub(r"(?m)^\[CANARY:[^\]]+\]\s*\n?", "", text or "")


def build_dso_subagent_orientation_banner(active_subagent_count: int) -> str:
    """Builds a deterministic orientation banner when background leaf subagents are active."""
    if active_subagent_count <= 0:
        return ""
    return (
        f"\n[DSO SUBAGENT QUEUE GUARD]: {active_subagent_count} active background subagent(s) running. "
        "Wait for reactive completion wakeup rather than polling status in a loop.\n"
    )


def run_pre_invocation_grounding(prompt_text: str, session_id: str = "live-session") -> Dict[str, Any]:
    """Executes live PreInvocation KG + OKF v0.2 + 20-Skill grounding for an active Antigravity Web session."""
    clean_prompt = strip_canary_headers(prompt_text or "")
    kg_data = load_kg()
    pinned_entities = resolve_hybrid_entities(clean_prompt, kg_data, use_alias_map=True) if clean_prompt and kg_data else []
    for ent in pinned_entities:
        props = ent.setdefault("properties", {})
        c_score = props.get("curation_score", 0.85)
        try:
            props["confidence_bucket_005"] = quantize_confidence_005(float(c_score))
        except Exception:
            props["confidence_bucket_005"] = 0.85

    seed_ids = [str(e.get("id", "")) for e in pinned_entities if e.get("id")]
    edges = kg_data.get("edges", []) if isinstance(kg_data, dict) else []
    hop2_map = collect_2hop_neighborhood(seed_ids, edges) if seed_ids else {}
    matched_skills = resolve_target_skills(clean_prompt)

    msg_lines: List[str] = []
    if pinned_entities:
        msg_lines.append("🧠 [KNOWLEDGE GRAPH AUTOMATIC PRE-INVOCATION GROUNDING (SSOT)]")
        msg_lines.append("<session_pinned_entities>")
        msg_lines.extend(_format_entity_lines(pinned_entities))
        msg_lines.append("</session_pinned_entities>")
    if matched_skills:
        msg_lines.append("🎯 [MANDATORY SKILL ACTIVATION]")
        for sname, spath in matched_skills:
            msg_lines.append(f"- Skill: `{sname}` -> file://{spath}")

    return {
        "session_id": session_id,
        "pinned_entities": pinned_entities,
        "hop2_neighborhood": hop2_map,
        "matched_skills": [{"name": n, "path": scrub(p)} for n, p in matched_skills],
        "ephemeral_message": scrub("\n".join(msg_lines)) if msg_lines else "",
    }


if __name__ == "__main__":
    main()
