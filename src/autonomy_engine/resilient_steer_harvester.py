#!/usr/bin/env python3
"""
Resilient Multi-Stage Preference & Steering Harvester (Clean-Room Standalone Edition).
Extracts mid-task user steering instructions (tau_i -> U_{i+1}) across 2 tiers:
- Tier 1: Fast-path declarative keyword sieve.
- Tier 2: Typo-tolerant informal directive alignment.
"""

import re
from typing import Tuple, List, Dict, Any

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

        return False, 0.0, "NOT_DECLARATIVE", text_clean, "TIER_REJECTED"


def harvest_steers_from_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts user steering rules from a list of transcript steps."""
    harvested = []
    seen = set()
    for step in steps:
        if step.get("type") == "USER_INPUT":
            content = str(step.get("content") or "").strip()
            for sentence in re.split(r"[\n\.]+", content):
                accepted, conf, f_mode, cleaned, tier = ResilientPreferenceSieve.evaluate(sentence)
                if accepted and cleaned.lower() not in seen:
                    seen.add(cleaned.lower())
                    harvested.append({
                        "rule": cleaned,
                        "confidence": conf,
                        "failure_mode": f_mode,
                        "tier": tier,
                    })
    return harvested
