#!/usr/bin/env python3
"""PreToolUse sentinel dispatcher. Fail-open by construction.

Contract for each rule module in rules/:
    def check(tool: str, args: dict, ctx: dict) -> dict | None
        Return None to abstain, or {"decision": ..., "reason": ...}.
        A rule that raises is treated as abstaining.
"""
import importlib.util
import json
import os
import pathlib
import sys

ALLOW = {"decision": "allow"}
SEVERITY = {
    "allow": 0,
    "overwrite": 1,
    "ask": 2,
    "deny_unless_prior_grant": 3,
    "force_ask": 4,
    "deny": 5,
}


def _load_rules(rules_dir: str):
    mods = []
    try:
        if not os.path.exists(rules_dir):
            return mods
        for p in sorted(pathlib.Path(rules_dir).glob("*.py")):
            if p.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(p.stem, str(p))
                if spec is None or spec.loader is None:
                    continue
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                if hasattr(m, "check"):
                    mods.append((p.stem, m))
            except Exception:
                continue
    except Exception:
        pass
    return mods


def main() -> int:
    verdict = ALLOW
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw or "{}")
        if not isinstance(payload, dict):
            payload = {}
        call = payload.get("toolCall") or {}
        if not isinstance(call, dict):
            call = {}
        tool = call.get("name") or payload.get("toolName") or ""
        args = call.get("args") or payload.get("toolArgs") or {}
        if not isinstance(args, dict):
            args = {}
        ctx = {
            "transcript_path": payload.get("transcriptPath", ""),
            "workspace_paths": payload.get("workspacePaths", []),
            "step_idx": payload.get("stepIdx", -1),
            "conversation_id": payload.get("conversationId", ""),
            "last_user_input": payload.get("lastUserInput", ""),
            "shadow": os.environ.get("SENTINEL_SHADOW", "0") == "1",
        }

        rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules")
        best = 0
        for _name, mod in _load_rules(rules_dir):
            try:
                r = mod.check(tool, args, ctx)
            except Exception:
                continue
            if not isinstance(r, dict):
                continue
            d = r.get("decision", "allow")
            if d == "allow" and "overwrite" in r:
                d = "overwrite"
            sev = SEVERITY.get(d, 0)
            if sev > best:
                best = sev
                verdict = dict(r)
                verdict["decision"] = d

        if ctx["shadow"] and verdict.get("decision") != "allow":
            try:
                log = os.environ.get(
                    "SENTINEL_SHADOW_LOG",
                    os.path.expanduser("~/.gemini/antigravity/telemetry/sentinel_ledger.jsonl"),
                )
                os.makedirs(os.path.dirname(log), exist_ok=True)
                with open(log, "a", encoding="utf-8") as f:
                    f.write(
                        json.dumps({
                            "tool": tool,
                            "step": ctx["step_idx"],
                            "would": verdict.get("decision"),
                            "reason": str(verdict.get("reason", ""))[:300],
                        })
                        + "\n"
                    )
            except Exception:
                pass
            verdict = ALLOW

        if verdict.get("decision") == "overwrite":
            verdict = {"decision": "allow", "overwrite": verdict.get("overwrite", {})}

    except Exception:
        verdict = ALLOW

    try:
        out = json.dumps(verdict)
    except Exception:
        out = '{"decision":"allow"}'
    sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.stdout.write('{"decision":"allow"}\n')
        sys.exit(0)
