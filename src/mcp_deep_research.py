"""FastMCP server exposing a single `deep_research` tool.

Two modes chosen by the caller:
  - standard: quick answer via one search + optionally one fetch (~5 tool turns).
  - max:      thorough report via multi-hop search + fetch loop (~15 tool turns).

Transports: Streamable HTTP (default) + SSE both mounted. Auth: prefers GCP
Application Default Credentials (ADC) via google-auth; falls back to
ANTHROPIC_API_KEY if ADC is unavailable.

Run:  python3 mcp_deep_research.py --port 8093 [--host 127.0.0.1]
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import logging
import os
import re
import socket
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import parse_qs, unquote, urlparse

import httpx

try:
    import google.auth
    import google.auth.transport.requests
    _HAVE_GOOGLE_AUTH = True
except Exception:
    _HAVE_GOOGLE_AUTH = False

from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("mcp_deep_research")

# --- Config -----------------------------------------------------------------
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "firsttestproject-343414")
VERTEX_MODEL = os.environ.get("MCP_VERTEX_MODEL", "claude-opus-4-8")
VERTEX_REGION = os.environ.get("MCP_VERTEX_REGION", "global")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

FETCH_TIMEOUT_S = 15.0
FETCH_MAX_CHARS = 40_000
SEARCH_MAX_RESULTS = 8
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

MODE_LIMITS = {
    # (max_tool_turns, max_tokens, max_fetches, max_searches)
    "standard": (5, 4096, 3, 2),
    "max":      (15, 16384, 12, 8),
}

TOOLS_SCHEMA = [
    {
        "name": "web_search",
        "description": (
            "Search the public web and return the top titles, URLs, and snippets. "
            "Use to discover pages when you don't already have a URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch a public https:// URL and return its rendered page as plain text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
]


# --- Auth -------------------------------------------------------------------
_ADC_CREDS = None


def _get_adc_token() -> str | None:
    """Return an ADC access token or None if ADC is not available."""
    global _ADC_CREDS
    if _HAVE_GOOGLE_AUTH:
        try:
            if _ADC_CREDS is None:
                _ADC_CREDS, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
            if not _ADC_CREDS.valid:
                _ADC_CREDS.refresh(google.auth.transport.requests.Request())
            if _ADC_CREDS.token:
                return _ADC_CREDS.token
        except Exception as e:
            log.warning(f"ADC token refresh via google.auth failed: {e}")

    # Fallback to GCE Metadata server
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            tok = data.get("access_token")
            if tok:
                return tok
    except Exception as e:
        log.debug(f"Metadata server token fetch failed: {e}")

    return None


# --- Tool implementations ---------------------------------------------------
def _ssrf_safe(url: str) -> tuple[bool, str]:
    try:
        pu = urlparse(url)
    except Exception as e:
        return False, f"bad url: {e}"
    if pu.scheme not in ("http", "https"):
        return False, f"scheme not allowed: {pu.scheme}"
    host = pu.hostname
    if not host:
        return False, "no host"
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception as e:
        return False, f"dns failed: {e}"
    for _, _, _, _, sockaddr in infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except Exception:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, f"host {host} → {ip} is not public"
    return True, "ok"


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.pending_href: str | None = None
        self.link_start: int | None = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "template", "svg"):
            self.skip_depth += 1
            return
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.pending_href = v
                    self.link_start = len(self.parts)
                    return
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template", "svg"):
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return
        if tag == "a" and self.pending_href is not None:
            if self.link_start is not None:
                inner = "".join(self.parts[self.link_start:]).strip()
                if inner:
                    self.parts.append(f" ({self.pending_href})")
            self.pending_href = None
            self.link_start = None
        if tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        self.parts.append(data)


def _html_to_text(html: str) -> str:
    p = _HTMLStripper()
    try:
        p.feed(html)
    except Exception:
        pass
    txt = "".join(p.parts)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n[ \t]*", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


async def _fetch_url(url: str) -> str:
    ok, reason = _ssrf_safe(url)
    if not ok:
        return f"[fetch_url refused: {reason}]"
    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT_S, follow_redirects=True,
            headers={"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml"},
        ) as cli:
            r = await cli.get(url)
    except Exception as e:
        return f"[fetch_url error: {e}]"
    ctype = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        return f"[fetch_url HTTP {r.status_code} for {url}]"
    body = r.text
    if "html" in ctype or "xml" in ctype:
        body = _html_to_text(body)
    truncated = ""
    if len(body) > FETCH_MAX_CHARS:
        body = body[:FETCH_MAX_CHARS]
        truncated = f"\n\n[... truncated at {FETCH_MAX_CHARS} chars]"
    return f"URL: {url}\nHTTP {r.status_code} {ctype}\n\n{body}{truncated}"


async def _web_search(query: str) -> str:
    q = query.strip()
    if not q:
        return "[web_search: empty query]"
    try:
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT_S, follow_redirects=True,
            headers={"User-Agent": BROWSER_UA},
        ) as cli:
            r = await cli.post("https://html.duckduckgo.com/html/", data={"q": q})
    except Exception as e:
        return f"[web_search error: {e}]"
    if r.status_code != 200:
        return f"[web_search HTTP {r.status_code}]"
    html = r.text
    result_pat = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
        r'.*?<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    strip_tags = re.compile(r"<[^>]+>")
    def _decode(href: str) -> str:
        if href.startswith("//"):
            href = "https:" + href
        try:
            pu = urlparse(href)
            if "duckduckgo.com" in pu.netloc and pu.path.startswith("/l/"):
                q_ = parse_qs(pu.query).get("uddg", [None])[0]
                if q_:
                    return unquote(q_)
        except Exception:
            pass
        return href
    lines = [f"Search results for: {q}\n"]
    for i, m in enumerate(result_pat.finditer(html), start=1):
        if i > SEARCH_MAX_RESULTS:
            break
        href = _decode(m.group(1))
        title = strip_tags.sub("", m.group(2)).strip()
        snippet = strip_tags.sub("", m.group(3)).strip()
        lines.append(f"{i}. {title}\n   {href}\n   {snippet}")
    if len(lines) == 1:
        return f"[web_search: no results for {q!r}]"
    return "\n".join(lines)


# --- Vertex / Anthropic call ------------------------------------------------
async def _call_claude(messages: list, max_tokens: int, timeout_s: float = 180.0) -> dict:
    """Call the Anthropic API — Vertex (via ADC) if available, else direct."""
    body = {
        "messages": messages,
        "max_tokens": max_tokens,
        "tools": TOOLS_SCHEMA,
    }
    token = _get_adc_token()
    if token:
        body["anthropic_version"] = "vertex-2023-10-16"
        base = "aiplatform.googleapis.com" if VERTEX_REGION == "global" else f"{VERTEX_REGION}-aiplatform.googleapis.com"
        loc = "global" if VERTEX_REGION == "global" else VERTEX_REGION
        url = f"https://{base}/v1/projects/{PROJECT}/locations/{loc}/publishers/anthropic/models/{VERTEX_MODEL}:rawPredict"
        hdrs = {
            "Authorization": f"Bearer {token}",
            "x-goog-user-project": PROJECT,
            "Content-Type": "application/json",
        }
    elif ANTHROPIC_API_KEY:
        body["model"] = VERTEX_MODEL.replace("claude-opus-4-8", "claude-opus-4-8")  # keep as-is
        url = "https://api.anthropic.com/v1/messages"
        hdrs = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
    else:
        raise RuntimeError("No auth: ADC unavailable and ANTHROPIC_API_KEY not set")
    async with httpx.AsyncClient(timeout=timeout_s) as cli:
        r = await cli.post(url, headers=hdrs, json=body)
    if r.status_code != 200:
        raise RuntimeError(f"Claude API {r.status_code}: {r.text[:400]}")
    return r.json()


async def _execute_tool(name: str, inp: dict) -> str:
    if name == "fetch_url":
        return await _fetch_url((inp or {}).get("url") or "")
    if name == "web_search":
        return await _web_search((inp or {}).get("query") or "")
    return f"[unknown tool: {name}]"


def _extract_text(content: list) -> str:
    text_parts, thinking_parts = [], []
    for b in content:
        t = b.get("type")
        if t == "text":
            text_parts.append(b.get("text", ""))
        elif t == "thinking":
            thinking_parts.append(b.get("thinking", ""))
    return ("".join(text_parts) or "".join(thinking_parts) or "").strip()


async def _research_loop(query: str, mode: str) -> dict:
    max_turns, max_tokens, max_fetches, max_searches = MODE_LIMITS[mode]
    system = (
        "You are a research assistant. Given a user query, plan a search strategy, "
        "issue tool calls to gather evidence, then produce a well-cited answer. "
        f"Mode: {mode!r} — you may make up to {max_fetches} fetch_url calls and "
        f"{max_searches} web_search calls, then STOP calling tools and answer. "
        "Cite sources inline as (url)."
    )
    messages = [{"role": "user", "content": f"{system}\n\nQuery: {query}"}]
    tool_history: list[str] = []
    fetches = searches = 0
    for turn in range(max_turns):
        try:
            resp = await _call_claude(messages, max_tokens=max_tokens)
        except Exception as e:
            return {"answer": f"[research error: {e}]", "tool_history": tool_history}
        content = resp.get("content", [])
        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if not tool_uses:
            return {
                "answer": _extract_text(content) or "[no text returned]",
                "tool_history": tool_history,
                "turns": turn + 1,
                "mode": mode,
            }
        messages.append({"role": "assistant", "content": content})
        results = []
        for tu in tool_uses:
            name = tu.get("name", "")
            inp = tu.get("input") or {}
            over_budget = (name == "fetch_url" and fetches >= max_fetches) or \
                          (name == "web_search" and searches >= max_searches)
            if over_budget:
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.get("id"),
                    "content": f"[{mode} mode budget reached for {name} — stop calling this tool and answer]",
                    "is_error": True,
                })
                continue
            if name == "fetch_url":
                fetches += 1
                tool_history.append(f"fetch_url {(inp.get('url') or '')[:80]}")
            elif name == "web_search":
                searches += 1
                tool_history.append(f"web_search {(inp.get('query') or '')[:80]}")
            log.info(f"[{mode}] turn={turn} tool={name} input={json.dumps(inp)[:120]}")
            try:
                out = await _execute_tool(name, inp)
            except Exception as ex:
                out = f"[tool exception: {ex}]"
            results.append({
                "type": "tool_result",
                "tool_use_id": tu.get("id"),
                "content": out,
            })
        messages.append({"role": "user", "content": results})
    return {
        "answer": "[research loop exhausted turn budget]",
        "tool_history": tool_history,
        "turns": max_turns,
        "mode": mode,
    }


# --- MCP wiring -------------------------------------------------------------
mcp = FastMCP(name="deep-research")


@mcp.tool(
    name="deep_research",
    description=(
        "Run a Claude-Opus-powered agentic research loop with web search and URL "
        "fetching. Returns a synthesized answer with inline URL citations. "
        "Modes: 'standard' (fast, ~5 tool turns) or 'max' (thorough, ~15 tool turns). "
        "The tool auto-authenticates via GCP ADC (Vertex Anthropic) or falls back to "
        "ANTHROPIC_API_KEY."
    ),
)
async def deep_research(
    query: str,
    mode: Literal["standard", "max"] = "standard",
) -> dict[str, Any]:
    if mode not in MODE_LIMITS:
        raise ValueError(f"mode must be 'standard' or 'max', got {mode!r}")
    if not query.strip():
        raise ValueError("query is required")
    log.info(f"[deep_research] mode={mode} query={query[:120]!r}")
    return await _research_loop(query.strip(), mode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8093)
    ap.add_argument("--transport", default="stdio",
                    choices=["http", "sse", "stdio"],
                    help="stdio = Standard IO for MCP client (default); http = Streamable HTTP; sse = SSE fallback")
    args = ap.parse_args()

    log.info(
        f"Starting deep-research MCP on {args.host}:{args.port} "
        f"({args.transport}); adc={'yes' if _get_adc_token() else 'no'}; "
        f"api_key={'yes' if ANTHROPIC_API_KEY else 'no'}; project={PROJECT}"
    )
    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # FastMCP 3.x supports "http" (Streamable HTTP) and "sse".
        mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
