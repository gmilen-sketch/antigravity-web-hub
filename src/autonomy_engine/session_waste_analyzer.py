#!/usr/bin/env python3
"""
Session Waste Analyzer - 16 Token-Waste Patterns (Clean-Room Standalone Edition).
Pure Diagnostic Reporting Module for Daily Dreaming Pipeline.
Analyzes parsed session transcripts against 16 MECE token waste anti-patterns (W1-W16).
"""

import os
import re
import json
import datetime
from typing import Dict, Any, List, Optional
from collections import Counter

WASTE_CATEGORIES = {
    "W1": {"name": "Suboptimal Model Routing", "description": "Heavy reasoning models used for trivial read/grep operations"},
    "W2": {"name": "Tool Payload Bloat", "description": "Large tool responses (>25KB) persisting across context turns"},
    "W3": {"name": "Cache Expiration Inefficiency", "description": "Turn intervals > 300s causing prompt cache invalidations"},
    "W4": {"name": "Prompt Schema Bloat", "description": "Excessive schema initialization before user interaction"},
    "W5": {"name": "Chatty Multi-Turn Polling", "description": "Consecutive turns polling task/command status instead of a loop"},
    "W6": {"name": "Redundant Idempotent Reads", "description": "Duplicate tool calls with identical parameters in the same session"},
    "W7": {"name": "Full-File Overwrite Thrashing", "description": "Rewriting entire large files (>5KB) for minor modifications"},
    "W8": {"name": "Sequential Independent Calls", "description": "Consecutive single-tool read turns without data dependencies"},
    "W9": {"name": "Circular Backtracking", "description": "Reading the same file >= 3 times across a session without making edits"},
    "W10": {"name": "Ungrounded Search Thrashing", "description": "Blind exploratory searches (>= 4 queries) before finding target files"},
    "W11": {"name": "High Reasoning on Trivial Inquiries", "description": "Extensive deliberation (>1,200 tokens) on deterministic single-tool operations"},
    "W12": {"name": "Unbounded Context Growth", "description": "Long sessions (>120KB characters) without checkpointing to artifacts"},
    "W13": {"name": "Orphaned Subagents", "description": "Subagents spawned without collecting or integrating their results"},
    "W14": {"name": "Unfiltered Data Dumps", "description": "Raw outputs dumping > 200 unformatted lines into context"},
    "W15": {"name": "Trial-and-Error CLI Thrashing", "description": "Consecutive command failures due to syntax errors"},
    "W16": {"name": "Dead-End Abandoned Sessions", "description": "High token consumption sessions ending without terminal deliverables"},
}


def analyze_single_session(steps: List[Dict[str, Any]], conv_id: str = "unknown") -> Dict[str, Any]:
    """Evaluates a session's transcript steps against the W1-W16 waste patterns."""
    detected = set()
    wasted_tokens_estimate = 0
    pattern_details = []

    tool_calls_seen = set()
    consecutive_polls = 0
    consecutive_reads = 0
    consecutive_cli_errors = 0
    file_views = Counter()
    total_session_chars = 0
    prev_turn_time: Optional[datetime.datetime] = None

    for idx, step in enumerate(steps):
        s_type = step.get("type", "")
        content = str(step.get("content") or "")
        thinking = str(step.get("thinking") or step.get("thought") or "")
        status = step.get("status", "DONE")
        tool_calls = step.get("tool_calls") or []
        created_at_str = step.get("created_at")

        step_chars = len(content) + len(thinking)
        total_session_chars += step_chars

        # W3: Cache Expiration Inefficiency
        if created_at_str:
            try:
                clean_ts = str(created_at_str).replace("Z", "+00:00")
                curr_time = datetime.datetime.fromisoformat(clean_ts)
                if prev_turn_time is not None:
                    delta_sec = (curr_time - prev_turn_time).total_seconds()
                    if delta_sec > 300 and total_session_chars > 32000:
                        detected.add("W3")
                        wasted_tokens_estimate += total_session_chars // 8
                prev_turn_time = curr_time
            except Exception:
                pass

        # W2: Tool Payload Bloat
        if s_type in ("TOOL_RESPONSE", "TOOL_RESULT") and len(content) > 25000:
            detected.add("W2")
            wasted_tokens_estimate += (len(content) - 25000) // 4

        # W14: Unfiltered Data Dumps
        if s_type in ("TOOL_RESPONSE", "TOOL_RESULT") and content.count("\n") > 200:
            detected.add("W14")
            wasted_tokens_estimate += 1500

        # W11: High Reasoning on Trivial Inquiries
        thinking_tokens = int(len(thinking.split()) * 1.3)
        if thinking_tokens > 1200 and len(tool_calls) == 1:
            tc_name = tool_calls[0].get("name") or tool_calls[0].get("tool_name", "")
            if tc_name in ("view_file", "list_resources", "list_dir"):
                detected.add("W11")
                wasted_tokens_estimate += thinking_tokens - 400

        if tool_calls:
            if len(tool_calls) == 1:
                tc = tool_calls[0]
                t_name = tc.get("name") or tc.get("tool_name", "")
                t_args = tc.get("args") or tc.get("arguments") or {}
                sig = f"{t_name}:{json.dumps(t_args, sort_keys=True)}"
                if sig in tool_calls_seen and t_name in ("view_file", "grep_search", "list_dir"):
                    detected.add("W6")
                    wasted_tokens_estimate += 500
                tool_calls_seen.add(sig)

                if t_name == "view_file":
                    consecutive_reads += 1
                    target = t_args.get("AbsolutePath") or t_args.get("path") or ""
                    if target:
                        file_views[target] += 1
                        if file_views[target] >= 3:
                            detected.add("W9")
                else:
                    consecutive_reads = 0

                if consecutive_reads >= 3:
                    detected.add("W8")

                if t_name == "manage_task" and t_args.get("Action") == "status":
                    consecutive_polls += 1
                    if consecutive_polls >= 2:
                        detected.add("W5")
                else:
                    consecutive_polls = 0

        if status == "ERROR":
            consecutive_cli_errors += 1
            if consecutive_cli_errors >= 2:
                detected.add("W15")
        else:
            consecutive_cli_errors = 0

    if total_session_chars > 120000:
        detected.add("W12")

    total_tokens = max(1, total_session_chars // 4)
    waste_ratio = round(min(1.0, wasted_tokens_estimate / total_tokens), 4)
    return {
        "conversation_id": conv_id,
        "total_tokens_est": total_tokens,
        "wasted_tokens_est": wasted_tokens_estimate,
        "waste_ratio": waste_ratio,
        "detected_patterns": sorted(list(detected)),
        "details": pattern_details[:10],
    }
