import json
import re
from typing import Dict, Any, List, Optional

class DivergenceHarvester:
    DECISION_TOOLS = {"run_command", "write_file", "replace_file_content", "git_commit", "deploy"}
    EXPLORATORY_TOOLS = {"code_search", "grep_search", "view_file", "list_dir", "read_document"}

    @classmethod
    def compute_dtdr(cls, steps: List[Dict[str, Any]]) -> float:
        decision_delib_tokens = []
        exploratory_delib_tokens = []
        for step in steps:
            thought = step.get("thought", "") or step.get("content", "")
            tokens = len(thought.split())
            tool_calls = step.get("tool_calls", [])
            tool_names = [c.get("name") or c.get("function", {}).get("name") for c in tool_calls]
            is_decision = any(t in cls.DECISION_TOOLS for t in tool_names)
            is_exploratory = any(t in cls.EXPLORATORY_TOOLS for t in tool_names)
            if is_decision:
                decision_delib_tokens.append(tokens)
            elif is_exploratory:
                exploratory_delib_tokens.append(tokens)
        mean_decision = sum(decision_delib_tokens) / max(len(decision_delib_tokens), 1)
        mean_exploratory = sum(exploratory_delib_tokens) / max(len(exploratory_delib_tokens), 1)
        return mean_decision / max(mean_exploratory, 1.0)

    @classmethod
    def classify_failure_mode(cls, user_intervention_text: str, prev_agent_output: str = "") -> str:
        text = user_intervention_text.lower()
        if any(k in text for k in ["invalid argument", "schema", "syntax error", "missing parameter"]):
            return "F1_SCHEMA_VIOLATION"
        elif any(k in text for k in ["you forgot", "context", "where is", "didn't know"]):
            return "F2_CONTEXT_GAP"
        elif any(k in text for k in ["think carefully", "rushed", "why didn't you check"]):
            return "F3_UNDER_DELIBERATION"
        elif any(k in text for k in ["format", "table", "layout", "active voice", "latex"]):
            return "F4_FORMATTING_BREACH"
        elif any(k in text for k in ["not done", "still failing", "incomplete", "didn't finish"]):
            return "F5_PREMATURE_COMPLETION"
        elif any(k in text for k in ["deprecated", "old model", "obsolete"]):
            return "F6_MODEL_DEPRECATION"
        return "F3_UNDER_DELIBERATION"
