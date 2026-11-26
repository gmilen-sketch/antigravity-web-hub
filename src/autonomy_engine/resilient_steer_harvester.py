#!/usr/bin/env python3
"""
Resilient Multi-Stage Preference & Steering Harvester (Clean-Room Standalone Edition).
Extracts mid-task user steering instructions (tau_i -> U_{i+1}) across 2 tiers:
- Tier 1: Fast-path declarative keyword sieve.
- Tier 2: Typo-tolerant informal directive alignment.
"""

import hashlib
import json
import os
import re
import sys
import urllib.request
from typing import Tuple, List, Dict, Any, Optional

WRAPPER_BLOCK_TAGS = (
    "CONTEXT_SUMMARY",
    "ADDITIONAL_METADATA",
    "USER_SETTINGS_CHANGE",
    "SYSTEM_MESSAGE",
    "EPHEMERAL_MESSAGE",
)
WRAPPER_BLOCK_RE = re.compile(
    r"(?is)<(" + "|".join(WRAPPER_BLOCK_TAGS) + r")\b[^>]*>.*?(?:</\1\s*>|\Z)"
)
USER_REQUEST_TAG_RE = re.compile(r"(?i)</?USER_REQUEST\b[^>]*>")


def strip_user_input_wrappers(raw_text: str) -> str:
    """Strips injected harness wrapper blocks (closed or truncated) and unwraps <USER_REQUEST>."""
    if not raw_text:
        return ""
    cleaned = WRAPPER_BLOCK_RE.sub(" ", str(raw_text))
    cleaned = USER_REQUEST_TAG_RE.sub(" ", cleaned)
    lines = [
        ln for ln in cleaned.splitlines()
        if not ln.strip().startswith("Error: The stream was interrupted")
    ]
    return "\n".join(lines).strip()


def _is_test_network_isolated() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("AGY_DISABLE_STEER_CLASSIFIER") == "1":
        return True
    return "unittest" in sys.modules or "pytest" in sys.modules


def _classify_ambiguous_steer_calibrated(text_clean: str) -> Optional[Tuple[bool, float]]:
    """Optional fail-open zero-output-token classifier fallback with /dev/shm caching."""
    endpoint = os.environ.get("AGY_STEER_CLASSIFIER_URL", "").strip()
    if not endpoint or _is_test_network_isolated():
        return None
    cache_dir = "/dev/shm" if (os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK)) else "/tmp"
    digest = hashlib.sha256(text_clean.lower().encode("utf-8")).hexdigest()[:16]
    cache_file = os.path.join(cache_dir, f"agw_steer_cls_{digest}.json")
    if os.path.isfile(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as fh:
                cached = json.load(fh)
            return bool(cached.get("accepted")), float(cached.get("confidence", 0.0))
        except Exception:
            pass
    try:
        body = json.dumps({"candidate": text_clean, "task": "durable_operator_steer"}).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=0.35) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        accepted = bool(payload.get("accepted") or payload.get("decision") == "ACCEPT")
        conf = float(payload.get("confidence", 0.91 if accepted else 0.0))
        try:
            with open(cache_file, "w", encoding="utf-8") as fh:
                json.dump({"accepted": accepted, "confidence": conf}, fh)
        except Exception:
            pass
        return accepted, conf
    except Exception:
        return None

COMMON_TYPO_MAP = {
    r"\balwayz\b": "always",
    r"\balwa+ys\b": "always",
    r"\balwayes\b": "always",
    r"\bnevr\b": "never",
    r"\bdont\s+evr\b": "never",
    r"\bdo\s+not\s+evr\b": "never",
    r"\bdont\b": "don't",
    r"\bplz\b": "please",
    r"\bswich\b": "switch",
    r"\bussing\b": "using",
    r"\bstopp\b": "stop",
    r"\bsupp+ort\b": "support",
}

REPEATED_CHARS = re.compile(r"(.)\1{2,}")

DECLARATIVE_KEYWORDS = [
    r"^(?:always|never|strictly (?:enforce|prohibit|require)|from now on,? always|make sure you always)\b",
    r"(?:\bmy preference is|\buser preference\s*:?|\bpreference\s*:?|\balways prefer|\bdefault to|\bstrictly prioritize)",
    r"(?:\bmandate\s*:?|\bprotocol\s*:?|\binvariant\s*:?)",
]

INFORMAL_KEYWORDS = [
    r"\b(?:lets?\s+)?(?:don't|do not|stop|avoid|refrain from)\s+(?:use|using|calling|running|generating|doing|outputting|editing|creating|syncing|updating)\b",
    r"\b(?:we have|lets?)\s+(?:removed|stopped|dropped)\s+(?:the\s+)?(?:updates?\s+to|support\s+for|using)\b",
    r"\b(?:drop|dropping|remove|removing|deprecated?)\s+support\s+for\b",
    r"\b(?:use|prefer|switch to|deliver|fetch|stage|keep|operate with|preserve|parameterize)\b.+?\b(?:instead of|rather than|over)\b",
    r"\b(?:going forward|in the future|next time|from now on|in subsequent turns)\b",
    r"\b(?:keep (?:all )?responses?|format (?:all )?(?:as|with)|show (?:only|raw)|no (?:yapping|fluff|apologies)|be more concise|never include)\b",
    r"\b(?:remember to always|you should always|you must always|make sure you always)\b",
    r"\b(?:don't|do not|stop|avoid)\s+\w+\s+directly,\s+(?:use|prefer)\b",
]

OPERATIONAL_EXCLUSIONS = [
    r"\bnever\s+mind\b",
    r"^(what|where|why|how|can we|can you|is there|did you|are we|do you|who|which)\b",
    r"\?$",
    r"^(check|find|tell|explain|show|look|ask|see|investigate|trace|simulate|analyse|analyze)\b",
    r"^(run|deploy|redeploy|destroy|sync|re-run|list|prepare|create|merge|open|restart|delete|remove|push|git)\b",
    r"^(graph\s+(?:TB|TD|LR|RL)|subgraph\b|```|\{|\}|\[)",
    r"^(again|oops|wait|no|yes|ok|okay|thanks|thank you|sorry)\b",
    r"^/black-hat-analysis\b",
]


def normalize_text(raw_text: str) -> str:
    text = raw_text.strip()
    text = REPEATED_CHARS.sub(r"\1\1", text)
    lower = text.lower()
    for pat, repl in COMMON_TYPO_MAP.items():
        lower = re.sub(pat, repl, lower)
    return lower


class ResilientPreferenceSieve:
    @staticmethod
    def evaluate(user_text: str) -> Tuple[bool, float, str, str, str]:
        text_clean = re.sub(r"^- #direct\s*", "", user_text).strip()
        if len(text_clean) < 12 or len(text_clean) > 300:
            return False, 0.0, "LENGTH_OUT_OF_BOUNDS", text_clean, "TIER_REJECTED"

        words = text_clean.split()
        if len(words) < 4 or len(words) > 45:
            return False, 0.0, "WORD_COUNT_OUT_OF_BOUNDS", text_clean, "TIER_REJECTED"

        norm = normalize_text(text_clean)

        for pat in OPERATIONAL_EXCLUSIONS:
            if re.search(pat, norm):
                has_prefix_override = bool(
                    re.match(
                        r"^(?:from now on|going forward|in the future|next time|user preference|my preference|mandate|invariant)\b",
                        norm,
                    )
                )
                if not has_prefix_override:
                    return False, 0.0, f"EXCLUSION:{pat[:25]}", text_clean, "TIER_REJECTED"

        if any(re.search(p, norm) for p in DECLARATIVE_KEYWORDS):
            return True, 0.95, "F3_TOOL_PLANNING", text_clean, "TIER_1_EXPLICIT"

        if any(re.search(p, norm) for p in INFORMAL_KEYWORDS):
            return True, 0.75, "F3_TOOL_PLANNING", text_clean, "TIER_2_INFORMAL"

        if any(re.search(p, norm) for p in [r"\b(?:ensure that all|make sure that all|we need to keep)\b"]):
            return True, 0.55, "AMBIGUOUS_SCOPE", text_clean, "TIER_AMBIGUOUS"

        calibrated = _classify_ambiguous_steer_calibrated(text_clean)
        if calibrated is not None and calibrated[0]:
            return True, calibrated[1], "F3_TOOL_PLANNING", text_clean, "TIER_3_CALIBRATED"

        return False, 0.0, "NOT_DECLARATIVE", text_clean, "TIER_REJECTED"


def audit_compaction_call_response_boundary(
    steps: List[Dict[str, Any]],
    proposed_split_index: int,
) -> Dict[str, Any]:
    """
    AGW-W12-03: Context Compaction Atomic Tool-Call/Response Pair Boundary Guard.
    Ensures transcript compaction never slices between a PLANNER_RESPONSE containing `tool_calls`
    and its immediately following TOOL_RESULT / GENERIC step, shifting the split boundary to
    preserve atomic call/response pairs and tracking preserved artifact paths.
    """
    n = len(steps or [])
    idx = max(0, min(int(proposed_split_index), n))
    adjusted_idx = idx
    if 0 < idx < n:
        prev_step = steps[idx - 1]
        if prev_step.get("tool_calls"):
            adjusted_idx = idx - 1

    preserved_paths = []
    for st in (steps or [])[:adjusted_idx]:
        for tc in st.get("tool_calls") or []:
            if isinstance(tc, dict):
                args = tc.get("args") or {}
                if isinstance(args, dict):
                    p = args.get("TargetFile") or args.get("Path") or args.get("AbsolutePath")
                    if isinstance(p, str) and p and p not in preserved_paths:
                        preserved_paths.append(p)

    return {
        "proposed_split_index": idx,
        "safe_split_index": adjusted_idx,
        "boundary_shifted": adjusted_idx != idx,
        "preserved_artifact_paths": preserved_paths,
    }


def harvest_steers_from_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts user steering rules from a list of transcript steps."""
    boundary_info = audit_compaction_call_response_boundary(steps, len(steps) // 2 if steps else 0)
    harvested = []
    seen = set()
    for step in steps:
        if step.get("type") == "USER_INPUT":
            content = strip_user_input_wrappers(str(step.get("content") or ""))
            if not content:
                continue
            for sentence in re.split(r"[\n\.]+", content):
                accepted, conf, f_mode, cleaned, tier = ResilientPreferenceSieve.evaluate(sentence)
                if accepted and cleaned.lower() not in seen:
                    seen.add(cleaned.lower())
                    harvested.append({
                        "rule": cleaned,
                        "confidence": conf,
                        "failure_mode": f_mode,
                        "tier": tier,
                        "safe_compaction_index": boundary_info["safe_split_index"],
                    })
    return harvested
