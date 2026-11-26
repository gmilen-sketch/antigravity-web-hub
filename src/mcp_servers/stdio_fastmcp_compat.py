#!/usr/bin/env python3
"""Role: Zero-Dependency MCP JSON-RPC 2.0 Stdio Compatibility Server (`stdio_fastmcp_compat`).

Purpose:
  Provides `FastMCP`, preferring the installed `fastmcp` package when present and falling back
  to a pure-stdlib Python 3.10+ Model Context Protocol (`2024-11-05` / `2025-03-26`) JSON-RPC 2.0
  `stdio` server supporting `initialize`, `notifications/initialized`, `ping`, `tools/list`,
  `tools/call` (sync and async), `resources/list`, and `prompts/list`. Ensures all 9 Python MCP
  servers work out-of-the-box on clean customer workstations without requiring `pip install fastmcp`.

How It Is Used:
  Imported by all Python MCP servers (`from mcp_servers.stdio_fastmcp_compat import FastMCP`)
  when launched via `mcp_config.json` or `.mcp.json`.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
import typing
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.dont_write_bytecode = True

try:
    from fastmcp import FastMCP as _RealFastMCP  # type: ignore[import-not-found]
    HAVE_FASTMCP = True
except ImportError:
    _RealFastMCP = None
    HAVE_FASTMCP = False


def _annotation_to_json_schema(ann: Any) -> Dict[str, Any]:
    if ann is inspect.Parameter.empty or ann is Any or ann is str:
        return {"type": "string"}
    if ann is bool:
        return {"type": "boolean"}
    if ann is int:
        return {"type": "integer"}
    if ann is float:
        return {"type": "number"}
    if ann is dict:
        return {"type": "object"}
    if ann is list:
        return {"type": "array", "items": {"type": "string"}}

    origin = typing.get_origin(ann)
    args = typing.get_args(ann)
    if origin is typing.Literal and args:
        return {"type": "string", "enum": [str(a) for a in args]}
    if origin in (list, List):
        item_schema = _annotation_to_json_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_schema}
    if origin in (dict, Dict):
        return {"type": "object"}
    if origin is typing.Union and args:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _annotation_to_json_schema(non_none[0])
    return {"type": "string"}


def _build_input_schema(fn: Callable[..., Any]) -> Dict[str, Any]:
    sig = inspect.signature(fn)
    try:
        hints = typing.get_type_hints(fn)
    except Exception:
        hints = {}
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        ann = hints.get(pname, param.annotation)
        prop_schema = _annotation_to_json_schema(ann)
        if param.default is inspect.Parameter.empty:
            required.append(pname)
        elif param.default is not None and isinstance(param.default, (str, int, float, bool)):
            prop_schema["default"] = param.default
        properties[pname] = prop_schema
    schema: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


class StdioFastMCP:
    """Pure-stdlib MCP JSON-RPC 2.0 stdio server compatible with `@mcp.tool()`."""

    def __init__(self, name: str = "mcp-server", **kwargs: Any) -> None:
        self.name = name or "mcp-server"
        self.version = str(kwargs.get("version") or "1.5.0")
        self._tools: Dict[str, Dict[str, Any]] = {}

    def tool(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            tname = name or fn.__name__
            tdesc = (description or inspect.getdoc(fn) or f"Execute {tname}.").strip()
            tmeta = dict(meta or kwargs.get("_meta") or {"antigravity/alwaysLoad": True})
            self._tools[tname] = {
                "fn": fn,
                "spec": {
                    "name": tname,
                    "description": tdesc,
                    "inputSchema": _build_input_schema(fn),
                    "_meta": tmeta,
                },
            }
            return fn

        return decorator

    def _call_tool_sync(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        entry = self._tools.get(tool_name)
        if entry is None:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            }
        fn = entry["fn"]
        sig = inspect.signature(fn)
        call_kwargs: Dict[str, Any] = {}
        accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        for k, v in (arguments or {}).items():
            if accepts_var_kw or k in sig.parameters:
                call_kwargs[k] = v
        try:
            if inspect.iscoroutinefunction(fn):
                raw_out = asyncio.run(fn(**call_kwargs))
            else:
                raw_out = fn(**call_kwargs)
            if isinstance(raw_out, str):
                text_out = raw_out
            else:
                text_out = json.dumps(raw_out, indent=2, ensure_ascii=False)
            return {
                "isError": False,
                "content": [{"type": "text", "text": text_out}],
            }
        except Exception as exc:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool error ({tool_name}): {exc}"}],
            }

    def handle_jsonrpc_message(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = str(msg.get("method") or "")
        has_id = "id" in msg
        req_id = msg.get("id")
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}

        if not has_id or method.startswith("notifications/"):
            return None

        if method == "initialize":
            client_proto = str(params.get("protocolVersion") or "2024-11-05")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": client_proto,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": self.version},
                },
            }
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": [t["spec"] for t in self._tools.values()]},
            }
        if method == "tools/call":
            tname = str(params.get("name") or "")
            targs = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": self._call_tool_sync(tname, targs),
            }
        if method == "resources/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}}
        if method == "prompts/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }

    @staticmethod
    def _read_next_message(stream: Any) -> Tuple[Optional[Dict[str, Any]], str]:
        while True:
            line = stream.readline()
            if not line:
                return None, "eof"
            if isinstance(line, bytes):
                line_str = line.decode("utf-8", errors="replace")
            else:
                line_str = line
            stripped = line_str.strip()
            if not stripped:
                continue
            if stripped.lower().startswith("content-length:"):
                length = int(stripped.split(":", 1)[1].strip())
                while True:
                    hdr = stream.readline()
                    if not hdr:
                        return None, "eof"
                    hdr_s = hdr.decode("utf-8", errors="replace") if isinstance(hdr, bytes) else hdr
                    if hdr_s in ("\r\n", "\n", ""):
                        break
                body = stream.read(length)
                body_s = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
                return json.loads(body_s), "content-length"
            return json.loads(stripped), "line"

    @staticmethod
    def _write_message(out_stream: Any, payload: Dict[str, Any], framing: str) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        if framing == "content-length":
            raw_bytes = encoded.encode("utf-8")
            header = f"Content-Length: {len(raw_bytes)}\r\n\r\n".encode("ascii")
            out_stream.write(header + raw_bytes)
        else:
            out_stream.write((encoded + "\n").encode("utf-8"))
        out_stream.flush()

    def run(self, transport: str = "stdio", **kwargs: Any) -> None:
        in_buf = getattr(sys.stdin, "buffer", sys.stdin)
        out_buf = getattr(sys.stdout, "buffer", sys.stdout)
        while True:
            try:
                msg, framing = self._read_next_message(in_buf)
            except json.JSONDecodeError as exc:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {exc}"},
                }
                self._write_message(out_buf, err_resp, "line")
                continue
            if msg is None:
                break
            resp = self.handle_jsonrpc_message(msg)
            if resp is not None:
                self._write_message(out_buf, resp, framing)


FastMCP = _RealFastMCP if HAVE_FASTMCP else StdioFastMCP
