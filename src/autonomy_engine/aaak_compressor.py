import re
import json
from typing import Dict, Any, List, Union

class AAAKCompressor:
    ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
    ANSI_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")

    GH_ISSUE_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)")
    GH_PR_RE = re.compile(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)")
    DOCS_URL_RE = re.compile(r"https?://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)/[^\s\)]*")
    SHEETS_URL_RE = re.compile(r"https?://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)/[^\s\)]*")

    @classmethod
    def pass1_strip_noise(cls, text: str) -> str:
        if not text:
            return ""
        text = cls.ANSI_OSC_RE.sub("", text)
        text = cls.ANSI_ESCAPE_RE.sub("", text)
        lines = []
        for line in text.split("\n"):
            if "\r" in line:
                line = line.split("\r")[-1]
            lines.append(line)
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def pass2_alias_paths(cls, text: str, repo_root: str = "/workspace") -> str:
        if not text:
            return ""
        if repo_root:
            text = text.replace(repo_root, "//repo")
        text = cls.GH_ISSUE_RE.sub(r"gh#\1/\2#\3", text)
        text = cls.GH_PR_RE.sub(r"pr#\1/\2#\3", text)
        text = cls.DOCS_URL_RE.sub(r"gdoc://\1", text)
        text = cls.SHEETS_URL_RE.sub(r"gsheet://\1", text)
        return text

    @classmethod
    def pass3_pack_action_tuples(cls, tool_calls: List[Dict[str, Any]]) -> str:
        if not tool_calls:
            return ""
        packed = []
        for call in tool_calls:
            name = call.get("name") or call.get("function", {}).get("name") or "tool"
            args = call.get("arguments") or call.get("function", {}).get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    pass
            if isinstance(args, dict):
                formatted_args = []
                for k in sorted(args.keys()):
                    v = args[k]
                    v_str = json.dumps(v, ensure_ascii=False)
                    formatted_args.append(f"{k}={v_str}")
                arg_str = ", ".join(formatted_args)
            else:
                arg_str = str(args)
            packed.append(f"⟪CALL:{name}({arg_str})⟫")
        return "\n".join(packed)

    @classmethod
    def pack_result_frame(cls, tool_name: str, result: Union[str, Dict[str, Any]]) -> str:
        if isinstance(result, (dict, list)):
            result_str = json.dumps(result, ensure_ascii=False)
        else:
            result_str = str(result)
        result_str = cls.pass1_strip_noise(result_str)
        return f"⟪RESULT:{tool_name}: {result_str}⟫"

    @classmethod
    def compress_text(cls, text: str, repo_root: str = "/workspace") -> str:
        p1 = cls.pass1_strip_noise(text)
        p2 = cls.pass2_alias_paths(p1, repo_root=repo_root)
        return p2

    @classmethod
    def compress_transcript_step(cls, step: Dict[str, Any], repo_root: str = "/workspace") -> Dict[str, Any]:
        compressed = dict(step)
        if "content" in compressed and isinstance(compressed["content"], str):
            compressed["content"] = cls.compress_text(compressed["content"], repo_root=repo_root)
        if "tool_calls" in compressed and isinstance(compressed["tool_calls"], list):
            compressed["packed_action_tuples"] = cls.pass3_pack_action_tuples(compressed["tool_calls"])
        if "tool_output" in compressed:
            name = compressed.get("tool_name", "tool")
            compressed["packed_result_frame"] = cls.pack_result_frame(name, compressed["tool_output"])
        return compressed
