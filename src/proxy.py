import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import logging
import subprocess
import time
import json
import re
import os
import asyncio
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reverse_proxy")

UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)

def ensure_trajectory_exists(convo_id: str):
    """
    Ensures that a minimal valid trajectory exists on disk for the given convo_id
    to bypass the backend 'trajectory not found in any store' deadlock.
    """
    if not convo_id:
        return
    
    brain_dir = os.path.expanduser(f"~/.gemini/antigravity/brain/{convo_id}")
    logs_dir = os.path.join(brain_dir, ".system_generated", "logs")
    transcript_path = os.path.join(logs_dir, "transcript.jsonl")
    transcript_full_path = os.path.join(logs_dir, "transcript_full.jsonl")
    
    if not os.path.exists(transcript_path):
        try:
            logger.info(f"Dynamically provisioning placeholder trajectory files for ID: {convo_id}")
            os.makedirs(logs_dir, exist_ok=True)
            
            # Format a simple, valid initial step sequence
            now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            step_0 = {
                "step_index": 0,
                "source": "USER_EXPLICIT",
                "type": "USER_INPUT",
                "status": "DONE",
                "created_at": now_str,
                "content": f"<USER_REQUEST>\nInitial Session Restoration\n</USER_REQUEST>\n<ADDITIONAL_METADATA>\nThe current local time is: {now_str}.\n</ADDITIONAL_METADATA>"
            }
            step_1 = {
                "step_index": 1,
                "source": "MODEL",
                "type": "PLANNER_RESPONSE",
                "status": "DONE",
                "created_at": now_str
            }
            
            content = json.dumps(step_0) + "\n" + json.dumps(step_1) + "\n"
            
            with open(transcript_path, "w") as f:
                with open(transcript_full_path, "w") as f_full:
                    f.write(content)
                    f_full.write(content)
            
            logger.info(f"Successfully provisioned placeholder trajectory for {convo_id} at {transcript_path}")
        except Exception as e:
            logger.error(f"Failed to dynamically provision trajectory for {convo_id}: {e}")

app = FastAPI()

@app.get("/valid-trajectories")
async def valid_trajectories():
    """Lists conversation IDs that ran to completion (>=2 steps).

    A cascade whose .db has 0-1 steps is a stub from a failed race with no
    user-visible content — leaving it in localStorage causes the SPA to try
    resurrecting it on every load, which triggers the "trajectory not found"
    / "Agent execution terminated" errors the user was hitting. We delete
    those .db stubs here and only return real cascades so the client-side
    purge removes the corresponding localStorage entries.
    """
    import sqlite3
    # Check BOTH the hub's and agy's conversation stores. agy (the CLI-flavored
    # language_server we're actually using for RPCs) writes to its own dir.
    conv_dirs = [
        os.path.expanduser("~/.gemini/antigravity/conversations"),
        os.path.expanduser("~/.gemini/antigravity-cli/conversations"),
    ]
    ids = []
    for conv_dir in conv_dirs:
        try:
            if not os.path.isdir(conv_dir):
                continue
            for fname in os.listdir(conv_dir):
                if not fname.endswith(".db"):
                    continue
                stem = fname[:-3]
                if not UUID_PATTERN.match(stem):
                    continue
                path = os.path.join(conv_dir, fname)
                steps = -1
                try:
                    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                    cur = c.cursor()
                    tables = [r[0] for r in cur.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='steps'"
                    ).fetchall()]
                    if tables:
                        steps = cur.execute("SELECT COUNT(*) FROM steps").fetchone()[0]
                    c.close()
                except Exception as e:
                    logger.warning(f"Could not read {fname}: {e}")

                if steps >= 2:
                    ids.append(stem.lower())
                else:
                    try:
                        os.remove(path)
                        for suffix in ("-shm", "-wal"):
                            side = path + suffix
                            if os.path.exists(side):
                                os.remove(side)
                        logger.info(f"Deleted stub cascade {stem} from {conv_dir} (steps={steps})")
                    except Exception as e:
                        logger.warning(f"Failed to delete stub {fname}: {e}")
        except Exception as e:
            logger.error(f"Failed to list {conv_dir}: {e}")
    return JSONResponse(
        content={"ids": ids},
        headers={"cache-control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/provision-trajectory/{uuid}")
async def provision_trajectory(uuid: str):
    if UUID_PATTERN.match(uuid):
        logger.info(f"Received API request to provision trajectory for UUID: {uuid}")
        ensure_trajectory_exists(uuid)
        return {"status": "success", "uuid": uuid}
    else:
        logger.warning(f"Invalid UUID received for provisioning: {uuid}")
        return {"status": "invalid_uuid", "uuid": uuid}


# The hub language_server binary serves the SPA HTML but its cloudcode-pa
# calls fail (project not allowlisted). The agy CLI binary contains a fully
# authenticated language_server serving on a random 127.0.0.1 port — RPCs go
# there. HTML/assets keep coming from the hub.
HUB_PORT = 8081

def find_agy_rpc_port():
    """Auto-discover the language_server port inside the running `agy` CLI.
    agy listens on two random 127.0.0.1 ports; the HTTP one accepts requests
    on / with 404, the HTTPS one refuses HTTP with 400."""
    import subprocess, re
    try:
        pids = subprocess.check_output(["pgrep", "-f", "/agy$"], text=True).split()
    except subprocess.CalledProcessError:
        return None
    for pid in pids:
        try:
            out = subprocess.check_output(
                ["ss", "-tlnp"], text=True, stderr=subprocess.DEVNULL
            )
        except Exception:
            return None
        for line in out.splitlines():
            m = re.search(rf"127\.0\.0\.1:(\d+).*pid={pid},", line)
            if not m:
                continue
            port = int(m.group(1))
            try:
                import httpx as _h
                r = _h.get(f"http://127.0.0.1:{port}/", timeout=2)
                # HTTP one gives 404 "page not found"; HTTPS one gives 400
                if r.status_code == 404 and "page not found" in r.text.lower():
                    return port
            except Exception:
                continue
    return None

AGY_RPC_PORT = find_agy_rpc_port()
logger.info(f"[startup] hub_port={HUB_PORT} agy_rpc_port={AGY_RPC_PORT}")

def upstream_port_for(path: str) -> int:
    """RPCs go to agy (real auth); HTML/JS/other assets go to hub."""
    if AGY_RPC_PORT and "/" in path and (
        path.startswith("exa.")
        or path.startswith("google.")
        or path.startswith("gemini_coder.")
    ):
        return AGY_RPC_PORT
    return HUB_PORT

shared_client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=50, max_connections=100),
    timeout=None,
)

# ============================================================================
# Protobuf wire-format helpers (minimal — just what we need for model injection).
# ============================================================================

def _varint(v: int) -> bytes:
    out = bytearray()
    while v > 0x7f:
        out.append((v & 0x7f) | 0x80)
        v >>= 7
    out.append(v & 0x7f)
    return bytes(out)

def _tag(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)

def _len_delim(field: int, payload: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(payload)) + payload

def _varint_field(field: int, value: int) -> bytes:
    return _tag(field, 0) + _varint(value)


# User-configured dropdown. Real Model enum values (from language_server binary
# descriptors) so protojson unmarshal accepts them. Actual upstream model is
# forced by --override_model_name=gemini-3.5-flash regardless of which is picked.
DROPDOWN_MODELS = [
    # ALL models route through our Vertex shim now — agy's Gemini path is
    # broken in the "external" build (GetChatMessage is unimplemented).
    # Order = display order in the dropdown. Gemini first = default.
    ("Gemini 3.5 Flash",              312),  # cosmetic enum; label is what routes
    ("Gemini 3.1 Flash Lite Preview", 314),
    ("Gemini 3.1 Pro",                313),
    ("Claude Opus 4.8",               290),
    ("Claude Fable 5",                340),
]
DEFAULT_MODEL_ENUM = 312

# Model labels routed via Vertex direct. The value is the Vertex publisher
# model ID and region. Called with the ADC token.
GEMINI_MODELS = {
    "Gemini 3.5 Flash":              {"publisher": "google", "model": "gemini-3.5-flash",              "region": "global"},
    "Gemini 3.1 Flash Lite Preview": {"publisher": "google", "model": "gemini-3.1-flash-lite-preview", "region": "global"},
    "Gemini 3.1 Pro":                {"publisher": "google", "model": "gemini-3.1-pro-preview",         "region": "global"},
}
CLAUDE_MODELS = {
    "Claude Opus 4.8": {"publisher": "anthropic", "model": "claude-opus-4-8", "region": "global"},
    "Claude Fable 5":  {"publisher": "anthropic", "model": "claude-fable-5",  "region": "global"},
}

def _vendor_for(label: str) -> str | None:
    if label in GEMINI_MODELS: return "gemini"
    if label in CLAUDE_MODELS: return "claude"
    return None

def _model_config_for(label: str) -> dict | None:
    return GEMINI_MODELS.get(label) or CLAUDE_MODELS.get(label)

SHIM_MODELS = {**GEMINI_MODELS, **CLAUDE_MODELS}

# In-memory state for shim cascades (both Gemini and Claude). cid -> entry.
# Historical name kept as CLAUDE_CASCADES for backward-compat with persisted
# JSON files; entries now carry a "vendor" field ("gemini" or "claude").
CLAUDE_CASCADES: dict = {}

# --- Persistent storage for Claude cascades ---------------------------------
# Cascade state lives on the data disk at /mnt/data (100 GB, ext4) so it
# survives restarts of antigravity-web.service. Each cascade is one JSON file.
_CASCADE_DIR_PRIMARY = "/mnt/data/antigravity/claude_cascades"
_CASCADE_DIR_FALLBACK = os.path.expanduser("~/.gemini/antigravity/claude_cascades")

def _cascade_dir() -> str:
    """Return an existing writable dir for cascade storage; prefer /mnt/data."""
    for d in (_CASCADE_DIR_PRIMARY, _CASCADE_DIR_FALLBACK):
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".probe")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return d
        except Exception:
            continue
    return _CASCADE_DIR_FALLBACK  # best-effort


def _cascade_path(cid: str) -> str:
    # Guard against traversal — cids are UUIDs but be safe.
    safe = re.sub(r"[^0-9a-fA-F-]", "", cid)[:64]
    return os.path.join(_cascade_dir(), f"{safe}.json")


def _persist_cascade(cid: str) -> None:
    """Write the current CLAUDE_CASCADES[cid] to disk (JSON). Best-effort."""
    entry = CLAUDE_CASCADES.get(cid)
    if not entry:
        return
    # Strip fields that aren't JSON-serializable or shouldn't persist.
    snap = {k: v for k, v in entry.items() if k not in ("model_config",)}
    try:
        p = _cascade_path(cid)
        tmp = p + ".tmp"
        with open(tmp, "w") as f:
            json.dump(snap, f)
        os.replace(tmp, p)
    except Exception as e:
        logger.warning(f"[CLAUDE] persist {cid} failed: {e}")


def _load_cascades_from_disk() -> None:
    """On startup, restore CLAUDE_CASCADES from disk. Re-attaches model_config
    from CLAUDE_MODELS by label."""
    d = _cascade_dir()
    count = 0
    try:
        files = os.listdir(d)
    except Exception:
        files = []
    for name in files:
        if not name.endswith(".json"):
            continue
        cid = name[:-5]
        path = os.path.join(d, name)
        try:
            with open(path) as f:
                snap = json.load(f)
        except Exception as e:
            logger.warning(f"[CLAUDE] load {cid} failed: {e}")
            continue
        # Reattach model_config; entries without a known label become
        # single-response read-only (still openable in the UI).
        label = snap.get("model_label") or ""
        snap["model_config"] = CLAUDE_MODELS.get(label)
        CLAUDE_CASCADES[cid] = snap
        count += 1
    if count:
        logger.info(f"[CLAUDE] loaded {count} persisted cascade(s) from {d}")


def _cascade_summary(cid: str, entry: dict) -> str:
    """Sidebar title for a Claude cascade — first line of the first prompt."""
    turns = entry.get("turns") or []
    for t in turns:
        p = t.get("prompt") or ""
        if p:
            line = p.strip().splitlines()[0].strip()
            return (line[:60] + "…") if len(line) > 60 else line
    return "New Claude conversation"


AGY_CONVO_DIRS = [
    os.path.expanduser("~/.gemini/antigravity/conversations"),
    os.path.expanduser("~/.gemini/antigravity-cli/conversations"),
]


def _agy_db_summaries() -> dict:
    """Enumerate agy's SQLite conversation DBs and produce synthetic summary
    entries so Gemini cascades appear in the sidebar (agy's own jetbox
    summary store is unused/uninitialized in standalone mode).

    Title extraction: step 0's step_payload is a proto blob. The user's
    prompt text is embedded as a length-prefixed string; we heuristically
    pull the first readable run of printable characters that contains a
    space (real prose) and isn't a UUID/hex string."""
    import sqlite3, re as _re
    updates: dict = {}
    uuid_only = _re.compile(r"^[0-9a-f-]+$", _re.I)
    printable = _re.compile(rb"[\x20-\x7e]{4,300}")
    # projectId candidates found in real .db files include "default-cli-project"
    # and any string that isn't a UUID. Heuristic: pick strings with a dash
    # or ending in "-project" / "-workspace" or explicit fallback.
    project_hint = _re.compile(r"^[a-z0-9][a-z0-9\-_.]{2,120}$", _re.I)
    for d in AGY_CONVO_DIRS:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith(".db"):
                continue
            cid = name[:-3]
            if not UUID_PATTERN.fullmatch(cid):
                continue
            if cid in CLAUDE_CASCADES:
                continue  # Claude entry wins — richer state
            path = os.path.join(d, name)
            title = "Untitled Conversation"
            project_id = "default-cli-project"  # fallback
            try:
                c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1.0)
                # Title from step 0's step_payload
                row = c.execute(
                    "SELECT step_payload FROM steps WHERE idx=0"
                ).fetchone()
                if row and row[0]:
                    for chunk in printable.findall(row[0]):
                        s = chunk.decode("ascii", errors="replace").strip()
                        s = _re.sub(r"^[^A-Za-z0-9/]+", "", s)
                        if len(s) < 8 or uuid_only.match(s):
                            continue
                        if " " in s:
                            title = s[:80] + ("…" if len(s) > 80 else "")
                            break
                # projectId from trajectory_metadata_blob (proto text scan)
                row = c.execute(
                    "SELECT data FROM trajectory_metadata_blob"
                ).fetchone()
                if row and row[0]:
                    for chunk in printable.findall(row[0]):
                        s = chunk.decode("ascii", errors="replace").strip()
                        s = _re.sub(r"^[^A-Za-z0-9/]+", "", s)
                        # Skip the trajectory_id / cascade_id UUIDs and short noise.
                        if uuid_only.match(s) or len(s) < 5:
                            continue
                        if project_hint.match(s):
                            project_id = s[:120]
                            break
                c.close()
            except Exception as e:
                logger.debug(f"[jetbox] {path}: {e}")
            try:
                from datetime import datetime, timezone
                ts_iso = datetime.fromtimestamp(
                    os.path.getmtime(path), tz=timezone.utc
                ).isoformat().replace("+00:00", "Z")
            except Exception:
                ts_iso = None
            updates[cid] = {
                "source": 0,
                "cascadeId": cid,
                "conversationId": cid,
                "summary": title,
                "trajectoryType": 1,
                "notFullyIdle": False,
                "waitingSteps": [],
                "status": 0,
                "annotations": {},
                "workspaces": [],
                "lastModifiedTime": ts_iso,
                # projectId is what the SPA groups by. Without it, entries land
                # in the "outside-of-project" bucket, invisible under any
                # named project (including Default project).
                "trajectoryMetadata": {"projectId": project_id},
            }
    return updates


def _shim_cascade_project(entry: dict) -> str:
    """Pick the projectId for a shim (Gemini/Claude) cascade summary.
    Uses whatever was captured at StartCascade time, else the default."""
    return entry.get("projectId") or "default-cli-project"


# --- FastMCP deep-research server, launched on demand via /mcp start ---------
MCP_BIN = os.path.expanduser("~/.gemini/antigravity/bin/mcp_deep_research.py")
MCP_PORT = int(os.environ.get("MCP_DEEP_RESEARCH_PORT", "8093"))
MCP_URL = f"http://127.0.0.1:{MCP_PORT}/mcp"
MCP_STATE = {"proc": None, "started_at": None}

DEEP_RESEARCH_TOOL_SCHEMA = {
    "name": "deep_research",
    "description": (
        "Delegate a research task to the on-demand deep-research MCP server. "
        "Use for questions requiring multi-source synthesis with citations. "
        "Returns a synthesized answer with inline URL citations. "
        "Mode 'standard' is fast (~5 tool turns); 'max' is thorough (~15 turns). "
        "Available only after the user has run `/mcp start`."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The research question."},
            "mode":  {"type": "string", "enum": ["standard", "max"], "default": "standard"},
        },
        "required": ["query"],
    },
}


def _mcp_running() -> bool:
    proc = MCP_STATE.get("proc")
    return proc is not None and proc.poll() is None


async def _mcp_start() -> str:
    if _mcp_running():
        return f"MCP already running (pid={MCP_STATE['proc'].pid}, port={MCP_PORT})"
    if not os.path.exists(MCP_BIN):
        return f"[error] MCP binary not found at {MCP_BIN}"
    try:
        import subprocess
        proc = subprocess.Popen(
            ["python3", MCP_BIN, "--port", str(MCP_PORT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )
    except Exception as e:
        return f"[error] failed to spawn MCP: {e}"
    # Wait up to 8s for the port to open
    import socket as _s
    deadline = time.time() + 8
    while time.time() < deadline:
        try:
            with _s.create_connection(("127.0.0.1", MCP_PORT), timeout=0.3):
                MCP_STATE["proc"] = proc
                MCP_STATE["started_at"] = time.time()
                return (f"✅ deep-research MCP started (pid={proc.pid}, "
                        f"port={MCP_PORT}). The `deep_research` tool is now "
                        f"available to this Claude cascade — ask a research "
                        f"question and I will use it.")
        except Exception:
            time.sleep(0.2)
    proc.kill()
    return "[error] MCP failed to open port in 8s"


async def _mcp_stop() -> str:
    if not _mcp_running():
        return "MCP is not running."
    proc = MCP_STATE["proc"]
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except Exception:
        proc.kill()
    MCP_STATE["proc"] = None
    MCP_STATE["started_at"] = None
    return "🛑 deep-research MCP stopped."


def _mcp_status() -> str:
    if _mcp_running():
        uptime = int(time.time() - (MCP_STATE.get("started_at") or 0))
        return f"deep-research MCP: running (pid={MCP_STATE['proc'].pid}, port={MCP_PORT}, uptime={uptime}s)"
    return "deep-research MCP: stopped. Send `/mcp start` to launch."


async def _call_mcp_deep_research(query: str, mode: str) -> str:
    """Invoke the deep-research MCP tool via HTTP and return its answer text."""
    if not _mcp_running():
        return "[error] MCP is not running. Ask the user to run `/mcp start` first."
    try:
        from fastmcp.client import Client
        from fastmcp.client.transports import StreamableHttpTransport
    except Exception as e:
        return f"[error] fastmcp client not available: {e}"
    # max mode can spend a while; give it a big budget.
    timeout_s = 600.0 if mode == "max" else 180.0
    try:
        transport = StreamableHttpTransport(MCP_URL)
        async with Client(transport, timeout=timeout_s) as c:
            r = await c.call_tool("deep_research", {"query": query, "mode": mode})
        data = r.data if hasattr(r, "data") else None
        if isinstance(data, dict):
            ans = data.get("answer") or "[no answer]"
            hist = data.get("tool_history") or []
            hint = f"\n\n[deep_research: {data.get('mode')} mode, {data.get('turns')} turns, tools: {len(hist)}]"
            return ans + hint
        return "\n".join(getattr(b, "text", "") for b in (r.content or []))
    except Exception as e:
        return f"[error] deep_research call failed: {e}"


MAX_TOOL_TURNS = 8
MAX_TOOL_CALLS_PER_CASCADE = 20
FETCH_TIMEOUT_S = 15.0
FETCH_MAX_CHARS = 40_000
SEARCH_MAX_RESULTS = 8
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

CLAUDE_TOOLS = [
    {
        "name": "fetch_url",
        "description": (
            "Fetch a public web URL over HTTP(S) and return the rendered page as plain text. "
            "Use this when the user gives you a URL, when a search result looks worth reading, "
            "or when you need to verify a fact from a specific page. "
            "Do not use for private or intranet URLs — only public web pages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Fully-qualified https:// URL to fetch."},
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the public web for a query and return the top result titles, URLs, and snippets. "
            "Use this to discover pages when you don't already have a URL. "
            "Follow up with fetch_url on the most promising result to read its full content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "Execute a bash shell command on the local VM machine and return its exit code, stdout, and stderr. "
            "Use this to compile code, run test scripts, run build commands, check system status, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The exact bash shell command to execute."},
                "cwd": {"type": "string", "description": "Optional. The working directory to execute the command in. Defaults to the user's home directory."}
            },
            "required": ["command"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write the complete content string to a file at the specified absolute path on the local VM. "
            "Parent directories will be created automatically if they do not exist."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The absolute or expanded path of the file to write to (e.g. '/path/to/file.txt' or '~/file.txt')."},
                "content": {"type": "string", "description": "The complete file contents to write."}
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read and return the complete content of a file at the specified absolute or expanded path on the local VM."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The absolute or expanded path of the file to read (e.g. '/path/to/file.txt' or '~/file.txt')."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_dir",
        "description": (
            "List all files and subdirectories within the specified directory path on the local VM."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The absolute or expanded directory path to list. Defaults to home directory if not provided."}
            },
        },
    },
    {
        "name": "grep_search",
        "description": (
            "Search for a text pattern or string query inside files recursively within a target directory path on the local VM."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The absolute or expanded directory path to search within recursively."},
                "query": {"type": "string", "description": "The query string or regex pattern to search for."}
            },
            "required": ["query"],
        },
    },
]


def _ssrf_safe(url: str) -> tuple[bool, str]:
    """Return (ok, reason). Reject non-http(s), and hosts that resolve to
    RFC1918/link-local/loopback (the proxy runs on a GCP VM with a metadata
    endpoint at 169.254.169.254; do not let Claude fetch it)."""
    import socket, ipaddress
    from urllib.parse import urlparse
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
    for family, _, _, _, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except Exception:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, f"host {host} → {ip} is not public"
    return True, "ok"


def _html_to_text(html: str) -> str:
    """Convert HTML to plain text using stdlib html.parser. Drops script/style
    tags entirely and renders <a href> as `text (href)` so link targets survive."""
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self.skip_depth = 0
            self.pending_href: str | None = None
            self.link_text_start: int | None = None

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript", "template", "svg"):
                self.skip_depth += 1
                return
            if tag == "a":
                for k, v in attrs:
                    if k == "href" and v:
                        self.pending_href = v
                        self.link_text_start = len(self.parts)
                        return
            if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
                self.parts.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript", "template", "svg"):
                if self.skip_depth > 0:
                    self.skip_depth -= 1
                return
            if tag == "a" and self.pending_href is not None:
                if self.link_text_start is not None:
                    text = "".join(self.parts[self.link_text_start:]).strip()
                    if text:
                        self.parts.append(f" ({self.pending_href})")
                self.pending_href = None
                self.link_text_start = None
            if tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
                self.parts.append("\n")

        def handle_data(self, data):
            if self.skip_depth > 0:
                return
            self.parts.append(data)

    p = _P()
    try:
        p.feed(html)
    except Exception:
        pass
    text = "".join(p.parts)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
            r = await cli.post(
                "https://html.duckduckgo.com/html/",
                data={"q": q},
            )
    except Exception as e:
        return f"[web_search error: {e}]"
    if r.status_code != 200:
        return f"[web_search HTTP {r.status_code}]"
    html = r.text
    # Each result block: <a class="result__a" href="/l/?uddg=<encoded>">title</a>
    # followed by <a class="result__snippet">snippet</a>
    from urllib.parse import parse_qs, urlparse, unquote
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


async def _run_command(command: str, cwd: str | None = None) -> str:
    if not command:
        return "[run_command: empty command]"
    if not cwd:
        cwd = os.path.expanduser("~")
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return "[run_command error: execution timed out after 60 seconds]"
        
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")
        
        res = []
        if proc.returncode is not None:
            res.append(f"Exit code: {proc.returncode}")
        if stdout_str:
            res.append(f"--- Standard Output ---\n{stdout_str}")
        if stderr_str:
            res.append(f"--- Standard Error ---\n{stderr_str}")
        if not stdout_str and not stderr_str:
            res.append("(no output)")
        return "\n\n".join(res)
    except Exception as e:
        return f"[run_command error: {e}]"


async def _write_file(path: str, content: str) -> str:
    if not path:
        return "[write_file: empty path]"
    try:
        path = os.path.abspath(os.path.expanduser(path))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        def do_write():
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        await asyncio.to_thread(do_write)
        return f"Successfully wrote {len(content)} characters to {path}"
    except Exception as e:
        return f"[write_file error: {e}]"


async def _read_file(path: str) -> str:
    if not path:
        return "[read_file: empty path]"
    try:
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(path):
            return f"[read_file error: file not found at {path}]"
        if os.path.isdir(path):
            return f"[read_file error: {path} is a directory, not a file]"
        def do_read():
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        return await asyncio.to_thread(do_read)
    except Exception as e:
        return f"[read_file error: {e}]"


async def _list_dir(path: str) -> str:
    if not path:
        path = os.path.expanduser("~")
    try:
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(path):
            return f"[list_dir error: path not found at {path}]"
        if not os.path.isdir(path):
            return f"[list_dir error: {path} is a file, not a directory]"
        def do_list():
            items = os.listdir(path)
            lines = []
            for item in sorted(items):
                full = os.path.join(path, item)
                if os.path.isdir(full):
                    lines.append(f"[DIR]  {item}/")
                else:
                    try:
                        sz = os.path.getsize(full)
                    except Exception:
                        sz = 0
                    lines.append(f"[FILE] {item} ({sz} bytes)")
            return lines
        lines = await asyncio.to_thread(do_list)
        if not lines:
            return f"Directory {path} is empty."
        return f"Contents of {path}:\n" + "\n".join(lines)
    except Exception as e:
        return f"[list_dir error: {e}]"


async def _grep_search(path: str, query: str) -> str:
    if not path:
        path = os.path.expanduser("~")
    if not query:
        return "[grep_search: empty query]"
    try:
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(path):
            return f"[grep_search error: path not found at {path}]"
        cmd = ["grep", "-rn", "--exclude-dir=.git", "--exclude-dir=node_modules", query, path]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return "[grep_search error: search timed out after 30 seconds]"
        stdout_str = stdout.decode("utf-8", errors="replace")
        lines = stdout_str.splitlines()
        if not lines:
            return f"No matches found for {query!r} in {path}"
        output_limit = 150
        res_lines = lines[:output_limit]
        res = f"Found {len(lines)} matches for {query!r} in {path}:\n" + "\n".join(res_lines)
        if len(lines) > output_limit:
            res += f"\n... (truncated {len(lines) - output_limit} additional matches)"
        return res
    except Exception as e:
        return f"[grep_search error: {e}]"


async def _execute_tool(name: str, inp: dict) -> str:
    if name == "fetch_url":
        url = (inp or {}).get("url") or ""
        return await _fetch_url(url)
    if name == "web_search":
        q = (inp or {}).get("query") or ""
        return await _web_search(q)
    if name == "deep_research":
        q = (inp or {}).get("query") or ""
        mode = (inp or {}).get("mode") or "standard"
        return await _call_mcp_deep_research(q, mode)
    if name == "run_command":
        cmd = (inp or {}).get("command") or ""
        cwd = (inp or {}).get("cwd") or None
        return await _run_command(cmd, cwd)
    if name == "write_file":
        path = (inp or {}).get("path") or ""
        content = (inp or {}).get("content") or ""
        return await _write_file(path, content)
    if name == "read_file":
        path = (inp or {}).get("path") or ""
        return await _read_file(path)
    if name == "list_dir":
        path = (inp or {}).get("path") or ""
        return await _list_dir(path)
    if name == "grep_search":
        path = (inp or {}).get("path") or ""
        q = (inp or {}).get("query") or ""
        return await _grep_search(path, q)
    return f"[unknown tool: {name}]"


def _describe_tool(tu: dict) -> str:
    name = tu.get("name", "")
    inp = tu.get("input") or {}
    if name == "fetch_url":
        return f"Fetching {(inp.get('url') or '')[:120]}"
    if name == "web_search":
        return f"Searching: {(inp.get('query') or '')[:120]}"
    if name == "deep_research":
        return f"Deep research ({inp.get('mode', 'standard')}): {(inp.get('query') or '')[:100]}"
    if name == "run_command":
        return f"Executing: {(inp.get('command') or '')[:100]}"
    if name == "write_file":
        return f"Writing file: {(inp.get('path') or '')[:120]}"
    if name == "read_file":
        return f"Reading file: {(inp.get('path') or '')[:120]}"
    if name == "list_dir":
        return f"Listing directory: {(inp.get('path') or '')[:120]}"
    if name == "grep_search":
        return f"Searching files for: {(inp.get('query') or '')[:100]}"
    return f"Running {name}"


def _extract_text(content: list) -> str:
    text_parts, thinking_parts = [], []
    for block in content:
        t = block.get("type")
        if t == "text":
            text_parts.append(block.get("text", ""))
        elif t == "thinking":
            thinking_parts.append(block.get("thinking", ""))
    return ("".join(text_parts) or "".join(thinking_parts) or "").strip()


async def _vertex_post(model_cfg: dict, body: dict, timeout_s: float = 120.0,
                       method: str = "rawPredict") -> dict:
    """POST to Vertex publisher-models. `method` picks the endpoint suffix:
    'rawPredict' for Anthropic, 'generateContent' for Gemini."""
    token = get_valid_access_token()
    if not token:
        raise RuntimeError("no ADC token available")
    proj = (os.environ.get("GOOGLE_CLOUD_PROJECT")
            or _die("GOOGLE_CLOUD_PROJECT env var required"))
    reg = model_cfg["region"]; m = model_cfg["model"]
    publisher = model_cfg.get("publisher", "anthropic")
    base = "aiplatform.googleapis.com" if reg == "global" else f"{reg}-aiplatform.googleapis.com"
    loc = "global" if reg == "global" else reg
    url = f"https://{base}/v1/projects/{proj}/locations/{loc}/publishers/{publisher}/models/{m}:{method}"
    hdrs = {
        "Authorization": f"Bearer {token}",
        "x-goog-user-project": proj,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout_s) as cli:
        r = await cli.post(url, headers=hdrs, json=body)
    if r.status_code != 200:
        raise RuntimeError(f"Vertex {r.status_code}: {r.text[:400]}")
    return r.json()


# --- Gemini native (Vertex generateContent) --------------------------------
# Gemini uses `contents` / `parts` schema and functionDeclarations for tools.
# We translate CLAUDE_TOOLS into Gemini shape at call time so tool code
# stays vendor-neutral.

def _gemini_tool_declarations() -> list:
    """Translate CLAUDE_TOOLS (+ optional deep_research) into Gemini's
    tools.functionDeclarations schema. Same names/descriptions/params."""
    decls = []
    tools = list(CLAUDE_TOOLS)
    if _mcp_running():
        tools.append(DEEP_RESEARCH_TOOL_SCHEMA)
    for t in tools:
        decls.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "parameters": t.get("input_schema") or {"type": "object", "properties": {}},
        })
    return [{"functionDeclarations": decls}]


def _describe_tool_gemini(name: str, args: dict) -> str:
    if name == "fetch_url":
        return f"Fetching {(args.get('url') or '')[:120]}"
    if name == "web_search":
        return f"Searching: {(args.get('query') or '')[:120]}"
    if name == "deep_research":
        return f"Deep research ({args.get('mode','standard')}): {(args.get('query') or '')[:100]}"
    if name == "run_command":
        return f"Executing: {(args.get('command') or '')[:100]}"
    if name == "write_file":
        return f"Writing file: {(args.get('path') or '')[:120]}"
    if name == "read_file":
        return f"Reading file: {(args.get('path') or '')[:120]}"
    if name == "list_dir":
        return f"Listing directory: {(args.get('path') or '')[:120]}"
    if name == "grep_search":
        return f"Searching files for: {(args.get('query') or '')[:100]}"
    return f"Running {name}"


async def _call_vertex_gemini(model_cfg: dict, prompt: str,
                              entry: dict | None = None,
                              timeout_s: float = 120.0) -> str:
    """Call Vertex Gemini generateContent with tool-use loop. Mirrors
    _call_vertex_claude but in Gemini's request/response shape."""
    # Build contents from full turn history for multi-turn context.
    contents: list = []
    if entry and entry.get("turns"):
        for t in entry["turns"][:-1]:
            if t.get("prompt") is not None:
                contents.append({"role": "user", "parts": [{"text": t["prompt"]}]})
            if t.get("response") is not None:
                contents.append({"role": "model", "parts": [{"text": t["response"]}]})
        contents.append({"role": "user", "parts": [{"text": entry["turns"][-1].get("prompt") or prompt}]})
    else:
        contents.append({"role": "user", "parts": [{"text": prompt}]})

    body_base = {
        "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.7},
        "tools": _gemini_tool_declarations(),
    }
    tool_calls_made = 0
    try:
        for turn in range(MAX_TOOL_TURNS):
            body = {**body_base, "contents": contents}
            try:
                d = await _vertex_post(model_cfg, body, timeout_s=timeout_s,
                                       method="generateContent")
            except Exception as e:
                return f"[proxy: Vertex Gemini call failed: {e}]"
            cands = d.get("candidates", [])
            if not cands:
                return "[proxy: empty Gemini candidates]"
            model_content = cands[0].get("content", {}) or {}
            parts = model_content.get("parts", []) or []
            # Collect function calls in this turn
            fn_calls = [(p["functionCall"]) for p in parts if p.get("functionCall")]
            if not fn_calls:
                # Final text — concat all text parts
                text = "".join(p.get("text", "") for p in parts if "text" in p).strip()
                return text or "[proxy: empty Gemini response]"
            # Feed back the model's assistant turn with the function-call parts,
            # then send a user turn containing functionResponse parts.
            contents.append({"role": "model", "parts": parts})
            fn_response_parts = []
            for fc in fn_calls:
                name = fc.get("name", "")
                args = fc.get("args") or {}
                call_id = fc.get("id")
                if tool_calls_made >= MAX_TOOL_CALLS_PER_CASCADE:
                    fr = {
                        "name": name,
                        "response": {"content": "[tool cap reached — refusing more tool calls]"},
                    }
                    if call_id:
                        fr["id"] = call_id
                    fn_response_parts.append({"functionResponse": fr})
                    continue
                tool_calls_made += 1
                if entry is not None:
                    entry["tool_status"] = _describe_tool_gemini(name, args)
                    entry["tool_history"] = entry.get("tool_history", []) + [entry["tool_status"]]
                    logger.info(f"[GEMINI] tool_use {name} args={json.dumps(args)[:200]}")
                try:
                    out = await _execute_tool(name, args)
                except Exception as ex:
                    out = f"[tool exception: {ex}]"
                fr = {
                    "name": name,
                    "response": {"content": out},
                }
                if call_id:
                    fr["id"] = call_id
                fn_response_parts.append({"functionResponse": fr})
            if entry is not None:
                entry["tool_status"] = None
            contents.append({"role": "user", "parts": fn_response_parts})
        return "[proxy: Gemini tool loop exhausted after 8 turns]"
    finally:
        if entry is not None:
            entry["tool_status"] = None


async def _call_vertex(model_cfg: dict, prompt: str, vendor: str,
                       entry: dict | None = None,
                       timeout_s: float = 120.0) -> str:
    """Vendor-neutral dispatcher used by the cascade shim."""
    if vendor == "gemini":
        return await _call_vertex_gemini(model_cfg, prompt, entry=entry, timeout_s=timeout_s)
    return await _call_vertex_claude(model_cfg, prompt, entry=entry, timeout_s=timeout_s)


async def _call_vertex_claude(model_cfg: dict, prompt: str,
                              entry: dict | None = None,
                              timeout_s: float = 120.0) -> str:
    """Call Vertex Anthropic API with tool-use loop. If Claude issues tool_use
    blocks, execute the tools locally, feed the results back, and iterate up to
    MAX_TOOL_TURNS. Optional `entry` (a CLAUDE_CASCADES value) gets a
    `tool_status` field updated between turns so the SPA can render progress.

    Multi-turn: if `entry["turns"]` has more than one turn, prior user/assistant
    messages are included so Claude has full conversation context. The final
    turn is the current user message (its response is None until we return)."""
    messages: list = []
    if entry and entry.get("turns"):
        for t in entry["turns"][:-1]:
            if t.get("prompt") is not None:
                messages.append({"role": "user", "content": t["prompt"]})
            if t.get("response") is not None:
                messages.append({"role": "assistant", "content": t["response"]})
        messages.append({"role": "user", "content": entry["turns"][-1].get("prompt") or prompt})
    else:
        messages.append({"role": "user", "content": prompt})
    # Advertise the deep_research tool only when the MCP subprocess is live.
    tools = list(CLAUDE_TOOLS)
    if _mcp_running():
        tools.append(DEEP_RESEARCH_TOOL_SCHEMA)
    body_base = {
        "max_tokens": 8192,
        "anthropic_version": "vertex-2023-10-16",
        "tools": tools,
    }
    tool_calls_made = 0
    try:
        for turn in range(MAX_TOOL_TURNS):
            body = {**body_base, "messages": messages}
            try:
                d = await _vertex_post(model_cfg, body, timeout_s=timeout_s)
            except Exception as e:
                return f"[proxy: Vertex call failed: {e}]"
            content = d.get("content", [])
            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            if not tool_uses:
                text = _extract_text(content)
                return text or "[proxy: empty Claude response]"
            # Feed back the assistant's tool_use blocks
            messages.append({"role": "assistant", "content": content})
            results = []
            for tu in tool_uses:
                if tool_calls_made >= MAX_TOOL_CALLS_PER_CASCADE:
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": tu.get("id"),
                        "content": "[tool cap reached — refusing more tool calls this cascade]",
                        "is_error": True,
                    })
                    continue
                tool_calls_made += 1
                if entry is not None:
                    entry["tool_status"] = _describe_tool(tu)
                    entry["tool_history"] = entry.get("tool_history", []) + [_describe_tool(tu)]
                    logger.info(f"[CLAUDE] tool_use {tu.get('name')} input={json.dumps(tu.get('input') or {})[:200]}")
                try:
                    out = await _execute_tool(tu.get("name", ""), tu.get("input") or {})
                except Exception as ex:
                    out = f"[tool exception: {ex}]"
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.get("id"),
                    "content": out,
                })
            if entry is not None:
                entry["tool_status"] = None
            messages.append({"role": "user", "content": results})
        return "[proxy: tool loop exhausted after 8 turns]"
    finally:
        if entry is not None:
            entry["tool_status"] = None

def _synthesize_claude_state_frame(cascade_id: str, entry: dict, enveloped: bool = True) -> bytes:
    """Build a StreamAgentStateUpdates response frame (agy-compatible JSON)
    from the CLAUDE_CASCADES entry."""
    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    trajectory_id = entry.get("trajectory_id") or cascade_id
    exec_id = entry.get("execution_id") or cascade_id
    steps = []
    # Prefer the multi-turn history if present; fall back to legacy
    # prompt/response for cascades registered before the migration.
    turns = entry.get("turns") or []
    if not turns and entry.get("prompt"):
        turns = [{"prompt": entry["prompt"], "response": entry.get("response")}]

    for turn_ix, t in enumerate(turns):
        # USER_INPUT step for this turn
        if t.get("prompt") is not None:
            steps.append({
                "type": "CORTEX_STEP_TYPE_USER_INPUT",
                "status": "CORTEX_STEP_STATUS_DONE",
                "metadata": {
                    "createdAt": entry.get("created_at", now),
                    "source": "CORTEX_STEP_SOURCE_USER_EXPLICIT",
                    "executionId": exec_id,
                    "sourceTrajectoryStepInfo": {
                        "trajectoryId": trajectory_id,
                        "stepIndex": len(steps),
                        "cascadeId": cascade_id,
                    },
                },
                "userInput": {
                    "items": [{"text": t["prompt"]}],
                    "userResponse": t["prompt"],
                },
            })
        # PLANNER_RESPONSE step for this turn. In-progress only for the
        # LAST turn while tool loop is running.
        is_last = turn_ix == len(turns) - 1
        have_response = t.get("response") is not None
        show_progress = is_last and not have_response and (entry.get("tool_status") or entry.get("tool_history"))
        if have_response or show_progress:
            if have_response:
                lines = [f"✅ {x}" for x in (entry.get("tool_history") or [])] if is_last else []
                if lines:
                    planner_text = "\n\n".join(lines) + "\n\n" + t["response"]
                else:
                    planner_text = t["response"]
            else:
                lines = [f"✅ {x}" for x in (entry.get("tool_history") or [])]
                if entry.get("tool_status"):
                    lines.append(f"⏳ {entry['tool_status']}")
                planner_text = "\n\n".join(lines) or "Thinking…"
            step_status = "CORTEX_STEP_STATUS_DONE" if have_response else "CORTEX_STEP_STATUS_RUNNING"
            step = {
                "type": "CORTEX_STEP_TYPE_PLANNER_RESPONSE",
                "status": step_status,
                "metadata": {
                    "stepGenerationVersion": 1,
                    "createdAt": entry.get("created_at", now),
                    "viewableAt": now,
                    "finishedGeneratingAt": now if have_response else None,
                    "startedAt": entry.get("created_at", now),
                    "completedAt": now if have_response else None,
                    "source": "CORTEX_STEP_SOURCE_MODEL",
                    "modelUsage": {
                        "model": "MODEL_GOOGLE_GEMINI_2_5_FLASH",  # cosmetic
                        "apiProvider": "API_PROVIDER_ANTHROPIC",
                    },
                    "executionId": exec_id,
                    "sourceTrajectoryStepInfo": {
                        "trajectoryId": trajectory_id,
                        "stepIndex": len(steps),
                        "cascadeId": cascade_id,
                    },
                },
                "plannerResponse": {
                    "modifiedResponse": planner_text,
                    "messageId": f"bot-{cascade_id[:8]}-{turn_ix+1}",
                    "stopReason": "STOP_REASON_END_OF_TURN" if have_response else "STOP_REASON_UNSPECIFIED",
                },
            }
            step["metadata"] = {k: v for k, v in step["metadata"].items() if v is not None}
            steps.append(step)
    status = "CASCADE_RUN_STATUS_IDLE" if entry.get("response") is not None else "CASCADE_RUN_STATUS_RUNNING"
    payload = {
        "update": {
            "conversationId": cascade_id,
            "trajectoryId": trajectory_id,
            "status": status,
            "executableStatus": "CASCADE_RUN_STATUS_IDLE",
            "executorLoopStatus": status,
            "mainTrajectoryUpdate": {
                "stepsUpdate": {
                    "indices": list(range(len(steps))),
                    "steps": steps,
                    "totalLength": len(steps),
                    "pageBounds": {"startIndex": 0, "endIndexExclusive": len(steps)},
                },
                "trajectoryType": "CORTEX_TRAJECTORY_TYPE_CASCADE",
                "metadata": {
                    "createdAt": entry.get("created_at", now),
                    "rootConversationId": cascade_id,
                },
                "lastStepType": steps[-1]["type"] if steps else "CORTEX_STEP_TYPE_UNSPECIFIED",
                "parentReferences": [],
            },
            "subtrajectoryUpdates": {},
            "stepScopedSubtrajectoryUpdates": {},
            "fullyIdle": entry.get("response") is not None,
        }
    }
    data = json.dumps(payload).encode()
    if enveloped:
        return b"\x00" + len(data).to_bytes(4, "big") + data
    return data


def _build_cascade_model_config_data() -> bytes:
    """Wire-format CascadeModelConfigData with the DROPDOWN_MODELS list.
    Field numbers verified from binary:
      CascadeModelConfigData.client_model_configs = 1 (repeated message)
      CascadeModelConfigData.default_override_model_config = 3 (message)
      ClientModelConfig.label = 1 (string)
      ClientModelConfig.model_or_alias = 2 (message ModelOrAlias)
      ModelOrAlias.model = 1 (enum)
      DefaultOverrideModelConfig.model_or_alias = 1 (message)
      DefaultOverrideModelConfig.version_id = 2 (string)
    """
    def moa(enum_val: int) -> bytes:
        return _varint_field(1, enum_val)  # ModelOrAlias.model

    def client_model_config(label: str, enum_val: int) -> bytes:
        return (
            _len_delim(1, label.encode())          # label
            + _len_delim(2, moa(enum_val))         # model_or_alias
        )

    body = b""
    for label, enum_val in DROPDOWN_MODELS:
        body += _len_delim(1, client_model_config(label, enum_val))
    # default_override_model_config points at the first entry
    body += _len_delim(3,
        _len_delim(1, moa(DEFAULT_MODEL_ENUM))     # DefaultOverrideModelConfig.model_or_alias
        + _len_delim(2, b"1")                       # version_id
    )
    return body


def _user_status_augmentation() -> bytes:
    """Bytes to APPEND to a serialized GetUserStatusResponse: an additional
    user_status field (#1) whose sole content is cascade_model_config_data (#33).
    Proto3 message-typed fields merge across duplicate tags, so this adds the
    dropdown to whatever the real language_server returned.
    """
    cmcd = _build_cascade_model_config_data()
    user_status_extra = _len_delim(33, cmcd)      # UserStatus.cascade_model_config_data
    return _len_delim(1, user_status_extra)       # GetUserStatusResponse.user_status


_USER_STATUS_APPEND = None
def user_status_append() -> bytes:
    global _USER_STATUS_APPEND
    if _USER_STATUS_APPEND is None:
        _USER_STATUS_APPEND = _user_status_augmentation()
    return _USER_STATUS_APPEND

# ============================================================================

_token_cache = {"token": "", "expires_at": 0}

def get_valid_access_token() -> str:
    """Fetches and caches a fresh GCP OAuth access token using gcloud."""
    now = time.time()
    if now < _token_cache["expires_at"]:
        return _token_cache["token"]
    
    try:
        # Run gcloud to get a fresh application-default user access token
        token = subprocess.check_output(
            ["gcloud", "auth", "application-default", "print-access-token"],
            text=True
        ).strip()
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + 3000  # Cache for 50 minutes
        logger.info("Successfully fetched a fresh OAuth access token from gcloud.")
        return token
    except Exception as e:
        logger.error(f"Error fetching gcloud token: {e}")
        return ""

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy(request: Request, path: str):
    """
    Main reverse proxy routing handler.
    Intercepts authentication queries to bypass the onboarding barrier,
    injects window.nativeStorage HTML polyfills, and streams long-lived
    gRPC-Web connections cleanly without buffering.
    """
    # 1. Intercept authentication queries to bypass the unclickable login screen
    is_auth_mock = False
    mock_json_content = None
    
    # GetUserStatus is NOT mocked here anymore — the real language_server responds
    # with a valid binary UserStatus; the response-augmentation block below
    # appends a cascade_model_config_data with the user-configured model list.
    # (Old JSON mock kept only as fallback in case someone flips is_auth_mock.)
    if False and ("GetUserStatus" in path or "getUserStatus" in path):
        is_auth_mock = True
        mock_json_content = {
            "userStatus": {
                "name": "Argolis Developer",
                "email": "user@argolis.com",
                "apiKey": "argolis_local_key",
                "user": {
                    "name": "Argolis Developer",
                    "email": "user@argolis.com",
                    "apiKey": "argolis_local_key",
                },
                "planType": "PLAN_TYPE_PRO",
                "isLoggedOut": False,
                "cascadeModelConfigData": {
                    "clientModelConfigs": [
                        {
                            "label": "Gemini 3.5 Flash (Medium)",
                            "modelName": "gemini-3.5-flash-medium",
                            "modelLabel": "Gemini 3.5 Flash (Medium)",
                            "modelOrAlias": {
                                "choice": {
                                    "case": "model",
                                    "value": 348
                                }
                            },
                            "disabled": False,
                            "supportedMimeTypes": {}
                        },
                        {
                            "label": "Gemini 3.5 Flash (High)",
                            "modelName": "gemini-3.5-flash-high",
                            "modelLabel": "Gemini 3.5 Flash (High)",
                            "modelOrAlias": {
                                "choice": {
                                    "case": "model",
                                    "value": 353
                                }
                            },
                            "disabled": False,
                            "supportedMimeTypes": {}
                        },
                        {
                            "label": "Gemini 3.5 Flash (Low)",
                            "modelName": "gemini-3.5-flash-low",
                            "modelLabel": "Gemini 3.5 Flash (Low)",
                            "modelOrAlias": {
                                "choice": {
                                    "case": "model",
                                    "value": 352
                                }
                            },
                            "disabled": False,
                            "supportedMimeTypes": {}
                        },
                        {
                            "label": "Gemini 3.1 Pro (Low)",
                            "modelName": "gemini-3.1-pro-low",
                            "modelLabel": "Gemini 3.1 Pro (Low)",
                            "modelOrAlias": {
                                "choice": {
                                    "case": "model",
                                    "value": 343
                                }
                            },
                            "disabled": False,
                            "supportedMimeTypes": {}
                        },
                        {
                            "label": "Gemini 3.1 Pro (High)",
                            "modelName": "gemini-3.1-pro-high",
                            "modelLabel": "Gemini 3.1 Pro (High)",
                            "modelOrAlias": {
                                "choice": {
                                    "case": "model",
                                    "value": 347
                                }
                            },
                            "disabled": False,
                            "supportedMimeTypes": {}
                        },
                        {
                            "label": "Gemini 3 Flash",
                            "modelName": "gemini-3-flash",
                            "modelLabel": "Gemini 3 Flash",
                            "modelOrAlias": {
                                "choice": {
                                    "case": "model",
                                    "value": 328
                                }
                            },
                            "disabled": False,
                            "supportedMimeTypes": {}
                        }
                    ],
                    "defaultOverrideModelConfig": {
                        "versionId": "1",
                        "modelOrAlias": {
                            "choice": {
                                "case": "model",
                                "value": 348
                            }
                        }
                    }
                }
            }
        }
    elif "HasAuthToken" in path or "hasAuthToken" in path:
        is_auth_mock = True
        mock_json_content = {
            "hasToken": True,
            "isGcpTos": True
        }
    elif "GetAuthStatus" in path or "getAuthStatus" in path:
        is_auth_mock = True
        mock_json_content = {
            "authResult": {
                "hasValidAuth": True,
                "grantedScopes": ["https://www.googleapis.com/auth/cloud-platform"],
                "isGcpTos": True
            }
        }
    elif "GetCascadeNuxes" in path or "getCascadeNuxes" in path:
        is_auth_mock = True
        mock_json_content = {
            "nuxConfigs": [],
            "nuxes": []
        }

        
    if is_auth_mock:
        logger.info(f"Intercepting authentication request: {path}")
        resp_headers = {
            "cache-control": "no-cache, no-store, must-revalidate",
            "pragma": "no-cache",
            "expires": "0",
            "X-Accel-Buffering": "no"
        }
        # Include CSRF token cookie to satisfy SPA CSRF verification
        resp_headers["set-cookie"] = f"csrfToken={os.environ.get('CSRF_TOKEN', '')}; Path=/; SameSite=Lax; Secure"
        
        accept_header = request.headers.get("accept", "").lower()
        content_type_header = request.headers.get("content-type", "").lower()
        
        is_json = "json" in accept_header or "json" in content_type_header
        is_grpc_web = "grpc-web" in accept_header or "grpc-web" in content_type_header or "application/grpc" in content_type_header
        
        if is_json:
            if is_grpc_web:
                json_payload = json.dumps(mock_json_content).encode("utf-8")
                # 5-byte header: 0x00 flag + 4-byte big-endian length
                data_header = b"\x00" + len(json_payload).to_bytes(4, "big")
                # Trailer: grpc-status: 0
                trailer_payload = b"grpc-status: 0\r\n"
                trailer_header = b"\x80" + len(trailer_payload).to_bytes(4, "big")
                
                framed_payload = data_header + json_payload + trailer_header + trailer_payload
                resp_headers["content-type"] = "application/grpc-web+json"
                resp_headers["x-grpc-web"] = "1"
                return Response(content=framed_payload, status_code=200, headers=resp_headers)
            else:
                return JSONResponse(content=mock_json_content, status_code=200, headers=resp_headers)
        else:
            # Fallback to the binary GetUserStatus frame for non-JSON requests
            mock_payload = (
                b"\x00\x00\x00\x00v\ng\x08\x01\x1a\tMock User:\x14mock-user@google.com"
                b"\x8a\x02A\n\x18\n\x10gemini-3.5-flash\x12\x03\x08\xb8\x02P\x04"
                b"\x12 \n\x0bRecommended\x12\x11\x12\x10gemini-3.5-flash\x1a\x05\n\x03\x08"
                b"\xb8\x02\x12\x0b\x12\tMock Plan"
                b"\x80\x00\x00\x00\x10grpc-status: 0\r\n"
            )
            resp_headers["content-type"] = "application/grpc-web+proto"
            resp_headers["x-grpc-web"] = "1"
            return Response(content=mock_payload, status_code=200, headers=resp_headers)

    # Scan path and referer for trajectory UUIDs to dynamically provision missing ones
    for match in UUID_PATTERN.finditer(path):
        ensure_trajectory_exists(match.group(0))
        
    referer = request.headers.get("referer", "")
    for match in UUID_PATTERN.finditer(referer):
        ensure_trajectory_exists(match.group(0))

    # 2. Extract and format query parameters and request body
    method = request.method
    body = await request.body()
    query_params = request.query_params

    # --- Claude via Vertex-direct shim -----------------------------------
    # When the SPA picks a Claude label in the dropdown, the injected JS adds
    # x-user-model: <label> to cascade RPCs. We intercept the flow here and
    # serve the response from Vertex Anthropic instead of routing to agy.
    #
    # Also — if a cascade is already registered as a Claude cascade (e.g.
    # user re-opened it from the sidebar after restart), sticky-route to
    # Claude regardless of what the current x-user-model header claims. That
    # header reflects the dropdown chip, which resets to Gemini on page load.
    user_model = request.headers.get("x-user-model", "")
    cid_in_body = None
    if body:
        try:
            _txt = body.decode("utf-8", errors="ignore")
            _m = UUID_PATTERN.search(_txt)
            if _m:
                cid_in_body = _m.group(0)
        except Exception:
            pass
    if (user_model not in SHIM_MODELS
        and cid_in_body and cid_in_body in CLAUDE_CASCADES
        and CLAUDE_CASCADES[cid_in_body].get("model_label") in SHIM_MODELS):
        user_model = CLAUDE_CASCADES[cid_in_body]["model_label"]
        logger.info(f"[SHIM] sticky-route {cid_in_body} → {user_model} (header was {request.headers.get('x-user-model', '')!r})")
    if user_model in SHIM_MODELS:
        vendor = _vendor_for(user_model)  # "gemini" | "claude"
        model_cfg = _model_config_for(user_model)

        # StartCascade: return a synthetic cascadeId (the SPA passes its own,
        # we just echo it back and register). Also captures projectId from the
        # request body so this cascade later shows up under the right project
        # in the sidebar (Default project or a user-created one).
        if "StartCascade" in path:
            body_text = (body or b"").decode("utf-8", errors="ignore")
            m = UUID_PATTERN.search(body_text)
            cid = m.group(0) if m else str(__import__("uuid").uuid4())
            # projectId capture — SPA sends trajectoryMetadata.projectId in body.
            project_id = None
            try:
                # Body is grpc-web+json enveloped: 5-byte header + JSON.
                b2 = body or b""
                if len(b2) >= 5 and b2[0] in (0x00, 0x80):
                    plen = int.from_bytes(b2[1:5], "big")
                    b2 = b2[5:5+plen]
                doc = json.loads(b2.decode("utf-8"))
                project_id = (
                    doc.get("trajectoryMetadata", {}).get("projectId")
                    or doc.get("projectId")
                )
            except Exception:
                pass
            CLAUDE_CASCADES.setdefault(cid, {
                "model_label": user_model,
                "model_config": model_cfg,
                "vendor": _vendor_for(user_model) or "claude",
                "projectId": project_id or "default-cli-project",
                "trajectory_id": str(__import__("uuid").uuid4()),
                "execution_id": str(__import__("uuid").uuid4()),
                "created_at": __import__("datetime").datetime.now(
                    tz=__import__("datetime").timezone.utc
                ).isoformat().replace("+00:00", "Z"),
                "prompt": None,
                "response": None,
                "turns": [],
            })
            logger.info(f"[SHIM] StartCascade registered {cid} for {user_model} projectId={project_id or 'default-cli-project'}")
            _persist_cascade(cid)
            reply = json.dumps({"cascadeId": cid}).encode()
            data_frame = b"\x00" + len(reply).to_bytes(4, "big") + reply
            trailer = b"grpc-status: 0\r\n"
            trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
            return Response(content=data_frame + trailer_frame, status_code=200,
                            headers={"content-type": "application/grpc-web+json"})

        # SendUserCascadeMessage: extract prompt, kick off Vertex Claude call
        if "SendUserCascadeMessage" in path:
            try:
                # Strip envelope + parse JSON
                b = body
                if len(b) >= 5 and b[0] in (0x00, 0x80):
                    plen = int.from_bytes(b[1:5], "big")
                    b = b[5:5+plen]
                doc = json.loads(b.decode("utf-8"))
                cid = doc.get("cascadeId")
                items = doc.get("items", [])
                prompt = " ".join(i.get("text", "") for i in items if i.get("text"))
            except Exception as e:
                logger.error(f"[CLAUDE] failed to parse SendUserCascadeMessage: {e}")
                return Response(status_code=500)

            entry = CLAUDE_CASCADES.setdefault(cid, {
                "model_label": user_model,
                "model_config": model_cfg,
                "trajectory_id": str(__import__("uuid").uuid4()),
                "execution_id": str(__import__("uuid").uuid4()),
                "created_at": __import__("datetime").datetime.now(
                    tz=__import__("datetime").timezone.utc
                ).isoformat().replace("+00:00", "Z"),
                # Full multi-turn history rendered to the SPA as sequential
                # USER_INPUT / PLANNER_RESPONSE steps.
                "turns": [],
            })
            # Defensive: ensure "turns" exists for cascades registered before
            # the multi-turn migration.
            if "turns" not in entry:
                entry["turns"] = []
            # Push the new user turn onto history; response starts null.
            entry["turns"].append({"prompt": prompt, "response": None})
            entry["prompt"] = prompt          # kept for backward compat
            entry["response"] = None          # kept for backward compat
            entry["turn"] = len(entry["turns"])
            entry["tool_history"] = []        # per-turn tool history
            entry["tool_status"] = None
            entry["vendor"] = vendor
            logger.info(f"[SHIM] SendUserCascadeMessage {cid} turn={entry['turn']} vendor={vendor} model={user_model} prompt={prompt[:80]!r}")

            # Slash-command handler for MCP lifecycle. Runs BEFORE Vertex is
            # called so Claude tokens aren't spent on control commands.
            stripped = (prompt or "").strip()
            cmd_lower = stripped.lower()
            slash_reply: str | None = None
            if cmd_lower.startswith("/mcp"):
                arg = cmd_lower.split(None, 2)
                sub = arg[1] if len(arg) >= 2 else "status"
                if sub == "start":
                    slash_reply = await _mcp_start()
                elif sub == "stop":
                    slash_reply = await _mcp_stop()
                elif sub in ("status", "info", ""):
                    slash_reply = _mcp_status()
                else:
                    slash_reply = f"Unknown /mcp subcommand: {sub!r}. Try: start, stop, status."
            _persist_cascade(cid)  # persist the new user turn immediately
            if slash_reply is not None:
                # Record synthetic reply and skip Vertex round-trip
                entry["turns"][-1]["response"] = slash_reply
                entry["response"] = slash_reply
                logger.info(f"[CLAUDE] {cid} slash-command handled: {stripped[:80]!r}")
                _persist_cascade(cid)
            else:
                # Fire Vertex call in the background — passes entry so the
                # tool loop can publish "🔎 Searching…" / "📄 Fetching…" progress
                # that _synthesize_claude_state_frame surfaces to the UI. Passes
                # entry["turns"] so Vertex sees the full conversation history.
                async def _run(cid=cid, entry=entry, vendor=vendor, model_cfg=model_cfg):
                    try:
                        resp_text = await _call_vertex(model_cfg, prompt, vendor=vendor, entry=entry)
                        if entry["turns"] and entry["turns"][-1]["response"] is None:
                            entry["turns"][-1]["response"] = resp_text
                        entry["response"] = resp_text
                        logger.info(f"[SHIM] {cid} vendor={vendor} turn={entry['turn']} got response ({len(resp_text)}B, tools={len(entry.get('tool_history') or [])})")
                    except Exception as ex:
                        err = f"[proxy error: {ex}]"
                        if entry["turns"] and entry["turns"][-1]["response"] is None:
                            entry["turns"][-1]["response"] = err
                        entry["response"] = err
                        logger.error(f"[CLAUDE] {cid} error: {ex}")
                    finally:
                        _persist_cascade(cid)  # persist final response
                __import__("asyncio").create_task(_run())

            # Return success immediately
            data_frame = b"\x00\x00\x00\x00\x02{}"
            trailer = b"grpc-status: 0\r\n"
            trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
            return Response(content=data_frame + trailer_frame, status_code=200,
                            headers={"content-type": "application/grpc-web+json"})

    # GetTurnDiff for a Claude cascade — upstream doesn't know the trajectory,
    # so short-circuit with an empty diff to silence the "trajectory not found"
    # console error. SPA doesn't display file diffs for Claude-authored turns.
    if "GetTurnDiff" in path and body:
        try:
            b = body
            if len(b) >= 5 and b[0] in (0x00, 0x80):
                plen = int.from_bytes(b[1:5], "big")
                b = b[5:5+plen]
            sub_doc = json.loads(b.decode("utf-8"))
            cid = sub_doc.get("conversationId")
        except Exception:
            cid = None
        if cid and (cid in CLAUDE_CASCADES or user_model in SHIM_MODELS):
            data_frame = b"\x00\x00\x00\x00\x02{}"
            trailer = b"grpc-status: 0\r\n"
            trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
            return Response(content=data_frame + trailer_frame, status_code=200,
                            headers={"content-type": "application/grpc-web+json"})

    # StreamAgentStateUpdates for a Claude cascade — serve synthesized frames.
    # Also fires for the initial stream opened by the SPA immediately upon
    # generating the conversation UUID, BEFORE StartCascade registers the
    # cascade. In that case (x-user-model is a Claude label but we haven't seen
    # StartCascade yet) we still serve synthetic frames so the SPA doesn't
    # hit upstream and see "trajectory not found".
    if "StreamAgentStateUpdates" in path and body:
        try:
            b = body
            if len(b) >= 5 and b[0] in (0x00, 0x80):
                plen = int.from_bytes(b[1:5], "big")
                b = b[5:5+plen]
            sub_doc = json.loads(b.decode("utf-8"))
            cid = sub_doc.get("conversationId") or sub_doc.get("cascadeId")
        except Exception:
            cid = None
        want_shim = user_model in SHIM_MODELS
        if cid and (cid in CLAUDE_CASCADES or want_shim):
            if cid not in CLAUDE_CASCADES:
                CLAUDE_CASCADES[cid] = {
                    "model": user_model, "model_label": user_model,
                    "vendor": _vendor_for(user_model) or "claude",
                    "trajectory_id": cid, "execution_id": cid,
                    "prompt": None, "response": None, "turn": 0,
                    "turns": [],
                }
            logger.info(f"[SHIM] StreamAgentStateUpdates for {cid} → synthetic frames (model={user_model or 'unknown'})")
            import asyncio as _a
            entry = CLAUDE_CASCADES[cid]
            async def claude_stream():
                # Initial frame — may have no prompt yet (fresh convo).
                yield _synthesize_claude_state_frame(cid, entry)
                def _snap():
                    return (entry.get("turn", 0), entry.get("response"),
                            entry.get("tool_status"),
                            len(entry.get("tool_history") or []))
                last = _snap()
                for _ in range(1200):  # 10 min @ 500ms
                    await _a.sleep(0.5)
                    cur = _snap()
                    if cur != last:
                        yield _synthesize_claude_state_frame(cid, entry)
                        last = cur
                # Idle after timeout
                while True:
                    await _a.sleep(60)
            return StreamingResponse(
                claude_stream(), status_code=200,
                headers={"content-type": "application/grpc-web+json",
                         "X-Accel-Buffering": "no", "cache-control": "no-cache"},
            )

    # ---------------------------------------------------------------------

    # Scan raw body for trajectory UUIDs
    if body:
        try:
            body_text = body.decode("utf-8", errors="ignore")
            for match in UUID_PATTERN.finditer(body_text):
                ensure_trajectory_exists(match.group(0))
        except Exception:
            pass
            
    # AUTOMATIC MODEL INJECTION:
    if body:
        try:
            is_grpc_web_framed = False
            raw_json_data = body
            header_prefix = b""
            
            # Check for gRPC-web framing (0x00/0x80 flag + 4-byte big-endian length)
            if len(body) >= 5 and body[0] in (0x00, 0x80):
                payload_len = int.from_bytes(body[1:5], "big")
                if 5 + payload_len == len(body):
                    is_grpc_web_framed = True
                    header_prefix = body[:5]
                    raw_json_data = body[5:]
            
            body_json = json.loads(raw_json_data.decode("utf-8"))
            if isinstance(body_json, dict):
                modified = False

                # Verified against the language_server proto descriptors:
                # - StartCascadeRequest.requested_model is a Model enum
                #   (a plain model-name string fails protojson unmarshal there).
                # - Cascade config model resolution reads
                #   cascadeConfig.plannerConfig.{planModel: Model, requestedModel: ModelOrAlias}.
                #   Fields injected anywhere else are silently discarded (DiscardUnknown).
                # Any valid Gemini enum value satisfies resolution; the actual model sent
                # upstream is forced by --override_model_name=gemini-3.5-flash.
                MODEL_ENUM = "MODEL_GOOGLE_GEMINI_2_5_FLASH"

                def _is_unset_enum(v):
                    """protobuf-es serializes an unset enum as 0 or
                    'MODEL_UNSPECIFIED' — both mean the server will reject
                    with 'neither PlanModel nor RequestedModel specified'.
                    ModelOrAlias {model: ...} is 'unset' when the inner
                    value is missing / 0 / UNSPECIFIED."""
                    if v is None or v == 0 or v == "" or v == "MODEL_UNSPECIFIED":
                        return True
                    if isinstance(v, dict):
                        m = v.get("model", v.get("value"))
                        return m is None or m == 0 or m == "" or m == "MODEL_UNSPECIFIED"
                    return False

                if "StartCascade" in path:
                    if _is_unset_enum(body_json.get("requestedModel")) and \
                            _is_unset_enum(body_json.get("requested_model")):
                        body_json["requestedModel"] = MODEL_ENUM
                        modified = True

                is_cascade_request = (
                    "cascadeConfig" in body_json or
                    "GetSlashCommands" in path or "getSlashCommands" in path or
                    "SendPrompt" in path or "sendPrompt" in path or
                    "CascadeSendPrompt" in path or "cascadeSendPrompt" in path or
                    "SendUserCascadeMessage" in path or "sendUserCascadeMessage" in path
                )

                if is_cascade_request:
                    if "SendUserCascadeMessage" in path:
                        picked = request.headers.get("x-user-model", "(none)")
                        logger.info(f"[SendUserCascadeMessage-DEBUG] x-user-model={picked!r}")

                    cascade_config = body_json.setdefault("cascadeConfig", {})
                    if isinstance(cascade_config, dict):
                        planner_config = cascade_config.setdefault("plannerConfig", {})
                        if isinstance(planner_config, dict):
                            # Force valid enum whenever the SPA-supplied model
                            # is missing OR UNSPECIFIED. The SPA's protobuf-es
                            # doesn't have RIFTRUNNER in its enum schema and
                            # falls back to UNSPECIFIED on serialize — so we
                            # must override, not just fill defaults.
                            if _is_unset_enum(planner_config.get("planModel")):
                                planner_config["planModel"] = MODEL_ENUM
                                modified = True
                            if _is_unset_enum(planner_config.get("requestedModel")):
                                planner_config["requestedModel"] = {"model": MODEL_ENUM}
                                modified = True
                            # Disable agentic mode. In agentic mode the model
                            # must emit tool calls; --override_model_name=
                            # gemini-3.5-flash returns EMPTY output and the
                            # executor's EmptyOutputContinuationCheckHook
                            # retries forever (verified: 1183-step DB).
                            conv = planner_config.get("conversational")
                            if isinstance(conv, dict) and conv.get("agenticMode"):
                                conv["agenticMode"] = False
                                modified = True
                        # Belt-and-suspenders: also disable the retry hook
                        # server-side. This is CascadeExecutorConfig.field 14
                        # (verified in binary proto descriptors). Prevents
                        # runaway loops even if agenticMode injection is bypassed
                        # or the model still returns empty for other reasons.
                        executor_config = cascade_config.setdefault("executorConfig", {})
                        if isinstance(executor_config, dict) and \
                                not executor_config.get("disableEmptyOutputContinuation"):
                            executor_config["disableEmptyOutputContinuation"] = True
                            modified = True

                if modified:
                    new_json_data = json.dumps(body_json).encode("utf-8")
                    if is_grpc_web_framed:
                        new_len = len(new_json_data)
                        new_header = body[0:1] + new_len.to_bytes(4, "big")
                        body = new_header + new_json_data
                    else:
                        body = new_json_data
                    logger.info(f"Injected {MODEL_ENUM} into plannerConfig for request: {path}")
        except Exception:
            # Binary Connect / gRPC-Web (application/{connect,grpc-web}+proto) —
            # the real SPA path. json.loads() throws here; fall through to the
            # wire-level injector below.
            pass

    # --- Binary proto model injection (Connect / gRPC-Web binary) ---------
    # Field numbers extracted from the language_server binary's embedded
    # descriptors. In proto3 wire format, appending an additional occurrence of
    # a message-typed field to the outer message causes the parser to MERGE it
    # into any existing value — so we don't need to parse or rewrite what's
    # already in the request body, we just append the missing model fields.
    #
    # Encoded once at import time:
    #   CascadePlannerConfig.plan_model (field 1, enum) = 348 (RIFTRUNNER)
    #     wire: tag=0x08, varint(348) = dc 02          -> b"\x08\xdc\x02"
    #   CascadeConfig.planner_config (field 1, message)
    #     wire: tag=0x0a, len=3, {plan_model=348}      -> b"\x0a\x03\x08\xb8\x02"
    #
    # Only the outer wrapping (cascade_config field number) differs per RPC.
    if True:
        try:
            ctype_raw = request.headers.get("content-type", "").lower()
            # Strip parameters (";charset=..." etc.) then match STRICTLY.
            # Wrong permissive matching (e.g. startswith "application/proto"
            # matching "application/proto+json" or a stray JSON body) would
            # append 0x70... = 'p' into the body and blow up JSON unmarshal.
            ctype = ctype_raw.split(";", 1)[0].strip()
            enveloped_types = {
                "application/connect+proto",
                "application/grpc-web+proto",
                "application/grpc-web",
                "application/grpc+proto",
                "application/grpc",
            }
            raw_proto_types = {"application/proto"}
            # Never fire binary injection on any JSON content type — the SPA
            # actually sends `application/grpc-web+json` and already supplies
            # its own requestedModel. Appending binary tags to a JSON body
            # breaks unmarshal with "invalid value p at line 1:<len>".
            is_enveloped = ctype in enveloped_types and "json" not in ctype
            is_raw_proto = ctype in raw_proto_types and "json" not in ctype

            if is_enveloped or is_raw_proto:
                # Compute injection bytes for this RPC
                cascade_cfg_field = None
                if "GetSlashCommands" in path:
                    cascade_cfg_field = 1  # GetSlashCommandsRequest.cascade_config
                elif "SendUserCascadeMessage" in path:
                    cascade_cfg_field = 5  # SendUserCascadeMessageRequest.cascade_config
                extra = b""
                if cascade_cfg_field is not None:
                    inner = b"\x0a\x03\x08\xb8\x02"
                    cc_tag = (cascade_cfg_field << 3) | 2
                    extra = bytes([cc_tag, len(inner)]) + inner
                if "StartCascade" in path:
                    # StartCascadeRequest.requested_model (field 14, enum) = 348
                    extra += b"\x70\xb8\x02"

                if extra:
                    if is_raw_proto:
                        body = (body or b"") + extra
                        logger.info(f"Injected raw-proto model bytes (+{len(extra)}B) for {path}")
                    elif is_enveloped and body and len(body) >= 5 and body[0] in (0x00, 0x80):
                        payload_len = int.from_bytes(body[1:5], "big")
                        if 5 + payload_len == len(body):
                            new_payload = body[5:] + extra
                            new_header = bytes([body[0]]) + len(new_payload).to_bytes(4, "big")
                            body = new_header + new_payload
                            logger.info(f"Injected enveloped model bytes (+{len(extra)}B) for {path}")
        except Exception as e:
            logger.error(f"Binary proto model injection failed for {path}: {e}")

    
    # Forward CCPA outbounds (v1internal:*) to real cloudcode-pa.googleapis.com
    # with a valid Bearer token from ADC. The language_server is configured with
    # --cloud_code_endpoint=http://127.0.0.1:8082, so its own outbound CCPA calls
    # arrive here — we authenticate them using this VM's application-default
    # credentials (i.e. the user's GCP project) instead of the browser OAuth
    # flow the standalone binary would otherwise want.
    # agy's language_server doesn't initialize the jetbox subsystem, so these
    # two RPCs return "jetbox summaries store not initialized" and the SPA
    # spin-retries once a second forever, flooding the console. Intercept:
    #  - JetboxSubscribeToSummaries: hold the stream open with one empty
    #    initial frame so the SPA thinks it's subscribed and stops retrying.
    #  - JetboxWriteSummary: no-op success.
    if "JetboxSubscribeToSummaries" in path:
        import asyncio
        ctype = (request.headers.get("content-type") or "").lower()
        def _build_summary_frame():
            # updates: cascadeId -> summary object. SPA schema (extracted from
            # main.js): `.source` (0 or 18 = local, else external), `.summary`
            # (display title), `.trajectoryMetadata`, `.trajectoryType`,
            # `.lastModifiedTime.seconds`, `.annotations`, `.notFullyIdle`,
            # `.waitingSteps`, `.workspaces`, `.status`. Filter rule for the
            # sidebar drops entries that are archived, pinned, forks, subagents
            # (parentConversationId), or trajectoryType===22.
            # Claude cascades (from in-memory + persisted state on /mnt/data)
            updates: dict = {}
            for cid, entry in CLAUDE_CASCADES.items():
                if not entry.get("turns"):
                    continue
                # google.protobuf.Timestamp JSON encoding is a RFC3339 STRING,
                # not a {seconds: N} object — Connect protojson rejects the object.
                ts_iso = entry.get("created_at") or (
                    __import__("datetime").datetime.now(
                        tz=__import__("datetime").timezone.utc
                    ).isoformat().replace("+00:00", "Z")
                )
                updates[cid] = {
                    "source": 0,  # local
                    "cascadeId": cid,
                    "conversationId": cid,
                    "summary": _cascade_summary(cid, entry),
                    "trajectoryType": 1,  # CORTEX_TRAJECTORY_TYPE_CASCADE
                    "notFullyIdle": entry.get("response") is None and bool(entry.get("prompt")),
                    "waitingSteps": [],
                    "status": 0,
                    "annotations": {},
                    "workspaces": [],
                    "lastModifiedTime": ts_iso,
                    "trajectoryMetadata": {"projectId": _shim_cascade_project(entry)},
                }
            # Agy (Gemini) cascades read from ~/.gemini/antigravity/conversations/*.db
            # Claude cids win (already in `updates`); agy .db entries fill the rest.
            for cid, u in _agy_db_summaries().items():
                updates.setdefault(cid, u)
            payload = json.dumps({"updates": updates, "deletes": []}).encode()
            if "grpc-web" in ctype or "connect+" in ctype or "grpc+" in ctype:
                return b"\x00" + len(payload).to_bytes(4, "big") + payload
            return payload
        def _snap_all():
            # Snapshot both sources so the poller re-emits on either changing.
            claude = tuple(sorted(CLAUDE_CASCADES.keys()))
            titles = {c: _cascade_summary(c, e) for c, e in CLAUDE_CASCADES.items()}
            agy: tuple = ()
            for d in AGY_CONVO_DIRS:
                if os.path.isdir(d):
                    try:
                        agy = agy + tuple(sorted(
                            (n, int(os.path.getmtime(os.path.join(d, n))))
                            for n in os.listdir(d) if n.endswith(".db")
                        ))
                    except Exception:
                        pass
            return (claude, tuple(sorted(titles.items())), agy)
        async def hold_open():
            yield _build_summary_frame()
            last = _snap_all()
            while True:
                await asyncio.sleep(2)
                cur = _snap_all()
                if cur != last:
                    yield _build_summary_frame()
                    last = cur
        rct = ctype if ("grpc-web" in ctype or "connect" in ctype) else "application/grpc-web+json"
        return StreamingResponse(
            hold_open(),
            status_code=200,
            headers={"content-type": rct, "cache-control": "no-cache",
                     "X-Accel-Buffering": "no"},
        )
    if "JetboxWriteSummary" in path or "JetboxDeleteSummary" in path:
        ctype = (request.headers.get("content-type") or "").lower()
        if "grpc-web" in ctype or "connect+" in ctype or "grpc+" in ctype:
            # gRPC-Web/Connect enveloped: MUST include a trailer frame
            # (flag byte 0x80 + BE u32 len + trailer text), otherwise the
            # SPA throws "ConnectError: missing trailer".
            data = b"{}"
            data_frame = b"\x00" + len(data).to_bytes(4, "big") + data
            trailer = b"grpc-status: 0\r\n"
            trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
            body_out = data_frame + trailer_frame
            rct = "application/grpc-web+json"
        else:
            body_out = b"{}"
            rct = "application/json"
        return Response(content=body_out, status_code=200,
                        headers={"content-type": rct})

    is_ccpa = path.startswith("v1internal") or path.startswith("v1/") or "v1internal" in path
    if is_ccpa:
        # These come from the hub binary polling caches. Since agy handles all
        # real cascade traffic, the hub's cache refreshes don't matter — we
        # return a minimal successful shape instead of forwarding to real
        # cloudcode-pa (which returns 403 SERVICE_DISABLED on this project).
        if "loadCodeAssist" in path:
            return JSONResponse(content={"response": {"userTier": {
                "availableCredits": [{"creditType": 1, "creditAmount": 1000,
                                       "minimumCreditAmountForUsage": 0}]}}})
        if "fetchUserInfo" in path:
            return JSONResponse(content={"userSettings": {"telemetryEnabled": False}})
        if "fetchAvailableModels" in path or "listExperiments" in path:
            return JSONResponse(content={})

        token = get_valid_access_token()
        if not token:
            logger.error(f"CCPA forward: no ADC token; returning 500 for {path}")
            return Response(content="No ADC token available", status_code=500)

        raw_body = await request.body()
        # Preserve original client headers, but replace host + authorization.
        fwd_headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length", "authorization", "x-goog-user-project")
        }
        fwd_headers["authorization"] = f"Bearer {token}"
        fwd_headers["host"] = "cloudcode-pa.googleapis.com"
        fwd_headers["x-goog-user-project"] = os.environ.get(
            "GOOGLE_CLOUD_PROJECT", "${GOOGLE_CLOUD_PROJECT}"
        )

        upstream_url = f"https://cloudcode-pa.googleapis.com/{path}"
        logger.info(f"CCPA forward: {request.method} {path} -> real cloudcode-pa (ADC auth)")
        try:
            async with httpx.AsyncClient(timeout=60.0) as cli:
                up = await cli.request(
                    request.method, upstream_url,
                    params=request.query_params,
                    headers=fwd_headers,
                    content=raw_body,
                )
        except httpx.HTTPError as e:
            logger.error(f"CCPA forward failed for {path}: {e}")
            return Response(content=f"CCPA gateway error: {e}", status_code=502)

        # Strip hop-by-hop / content-length headers; httpx decompressed already.
        drop = {"content-length", "transfer-encoding", "connection",
                "keep-alive", "content-encoding"}
        resp_hdrs = {k: v for k, v in up.headers.items() if k.lower() not in drop}
        return Response(content=up.content, status_code=up.status_code, headers=resp_hdrs)

        
    # Copy headers and explicitly set Host header to target host
    headers = {}
    for k, v in request.headers.items():
        if k.lower() not in ("host", "content-length"):
            headers[k] = v
            
    upstream_port = upstream_port_for(path)
    headers["host"] = f"127.0.0.1:{upstream_port}"
    if "host" in request.headers:
        headers["x-forwarded-host"] = request.headers["host"]

    # Inject Authorization header ONLY for the hub upstream — agy already has
    # its own authenticated language_server and doesn't want a foreign token.
    if upstream_port == HUB_PORT:
        token = get_valid_access_token()
        if token:
            headers["authorization"] = f"Bearer {token}"

    # Strip 'dev-ui' prefix from the path to avoid React Router route trap
    clean_path = path
    if clean_path.startswith("dev-ui/"):
        clean_path = clean_path[len("dev-ui/"):]
    elif clean_path == "dev-ui":
        clean_path = ""
    url = f"/{clean_path}"
    full_url = f"http://127.0.0.1:{upstream_port}{url}"

    # 3. Handle HTML page request: read fully, decompress if needed, and inject nativeStorage polyfill
    if clean_path in ("", "index.html"):
        try:
            req = shared_client.build_request(
                method, full_url, params=query_params, headers=headers, content=body
            )
            resp = await shared_client.send(req)
        except httpx.HTTPError as exc:
            logger.error(f"Error forwarding HTML request to backend: {exc}")
            return Response(content="Gateway Error: Unable to connect to backend", status_code=502)
            
        exclude_headers = {
            "content-length", "transfer-encoding", 
            "connection", "keep-alive", "proxy-authenticate", 
            "proxy-authorization", "te", "trailers", "upgrade"
        }
        resp_headers = {
            k: v for k, v in resp.headers.items() if k.lower() not in exclude_headers
        }
        resp_headers["cache-control"] = "no-cache, no-store, must-revalidate"
        resp_headers["pragma"] = "no-cache"
        resp_headers["expires"] = "0"
        resp_headers["set-cookie"] = f"csrfToken={os.environ.get('CSRF_TOKEN', '')}; Path=/; SameSite=Lax; Secure"
        
        content = resp.content
        is_gzipped = resp.headers.get("content-encoding", "") == "gzip"
        if is_gzipped:
            import gzip
            try:
                html_text = gzip.decompress(content).decode("utf-8")
            except Exception:
                html_text = content.decode("utf-8", errors="ignore")
        else:
            html_text = content.decode("utf-8", errors="ignore")
            
        polyfill = """
<script>
  console.log("Injecting window.nativeStorage polyfill for standalone web hub...");
  window.nativeStorage = {
    getItems: async () => {
      const items = {};
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        items[key] = localStorage.getItem(key);
      }
      return items;
    },
    updateItems: async (items) => {
      for (const [key, value] of Object.entries(items)) {
        if (value === null || value === undefined) {
          localStorage.removeItem(key);
        } else {
          localStorage.setItem(key, value);
        }
      }
    },
    onChanged: (callback) => {
      const handler = (e) => {
        if (e.storageArea === localStorage) {
          const changes = {};
          changes[e.key] = e.newValue;
          callback(changes);
        }
      };
      window.addEventListener('storage', handler);
      return () => window.removeEventListener('storage', handler);
    }
  };

  // --- Model-picker → header bridge ---------------------------------
  // The SPA can't serialize custom Model enum values so it always sends
  // MODEL_UNSPECIFIED on the wire. To let the proxy know which dropdown
  // entry the user actually picked, we:
  //   1) Watch the model-selector button's text (a MutationObserver).
  //   2) When it changes, stash the label in window.__selectedModelLabel
  //      and localStorage (so it survives page reload).
  //   3) Wrap window.fetch to add an x-user-model header on cascade RPCs.
  window.__selectedModelLabel = localStorage.getItem('__selectedModelLabel') || 'Gemini 3.5 Flash';
  console.log('[model-picker] initial =', window.__selectedModelLabel);

  const KNOWN_LABELS = ['Gemini 3.5 Flash', 'Gemini 3.1 Flash Lite Preview',
                         'Gemini 3.1 Pro', 'Claude Opus 4.8', 'Claude Fable 5'];

  function _findModelChip() {
    // The chip is a leaf button whose visible text is exactly a known label
    // and which sits inside the input toolbar (below chat scroll, above nothing).
    for (const btn of document.querySelectorAll('button')) {
      const txt = (btn.innerText || btn.textContent || '').trim();
      if (KNOWN_LABELS.includes(txt) && btn.offsetParent !== null) {
        // Prefer chips that aren't inside a popover (role=menu / role=listbox).
        if (btn.closest('[role="menu"],[role="listbox"],[data-radix-popper-content-wrapper]')) continue;
        return btn;
      }
    }
    return null;
  }

  function _forceChipLabel(label) {
    // Locate the chip button and overwrite its innermost <span> text so the
    // UI reflects the user's choice even if the SPA's onClick didn't fire.
    const chip = _findModelChip();
    if (!chip) return false;
    // The label sits in a leaf <span> — replace the innermost text node.
    const spans = chip.querySelectorAll('span');
    const target = spans.length ? spans[spans.length - 1] : chip;
    if ((target.innerText || '').trim() !== label) target.innerText = label;
    return true;
  }

  // Timestamp of the last user-initiated click. Chip-transition events are
  // ignored while this is fresh — the SPA reverts the chip to its own idea of
  // the model shortly after user picks a "custom" enum, and we don't want to
  // let that revert clobber the user's actual choice.
  let __userClickAt = 0;
  function _setModel(label, source) {
    if (!KNOWN_LABELS.includes(label)) return;
    if (source === 'chip-transition' && (Date.now() - __userClickAt) < 5000) {
      // SPA reverted after user click — force chip back to user's choice.
      _forceChipLabel(window.__selectedModelLabel);
      return;
    }
    if (source === 'click') __userClickAt = Date.now();
    if (window.__selectedModelLabel === label) { _forceChipLabel(label); return; }
    window.__selectedModelLabel = label;
    try { localStorage.setItem('__selectedModelLabel', label); } catch (e) {}
    _forceChipLabel(label);
    console.log('[model-picker] selection ' + source + ' →', label);
  }

  // 1) Direct click interceptor (capture phase) — catches every user click on
  //    a popover option even if the SPA's React handler is a no-op for that
  //    enum value. Runs before the SPA's own delegated listeners.
  document.addEventListener('click', (e) => {
    let el = e.target;
    while (el && el !== document.body) {
      if (el.tagName === 'BUTTON') {
        const txt = (el.innerText || el.textContent || '').trim();
        if (KNOWN_LABELS.includes(txt)) {
          // A popover option button lives inside role="dialog" (Radix Popover).
          // The chip itself is not inside that dialog. Use that to disambiguate.
          const inPopover = !!el.closest('[role="dialog"],[role="menu"],[role="listbox"]');
          if (inPopover) {
            _setModel(txt, 'click');
            setTimeout(() => document.body.dispatchEvent(
              new KeyboardEvent('keydown', {key:'Escape', bubbles:true})), 0);
          }
          return;
        }
      }
      el = el.parentElement;
    }
  }, true);

  // --- Folder picker shim (File System Access API) --------------------
  // The SPA's "Add Folder" button expects a desktop Electron file dialog
  // that isn't wired in the web hub. Intercept the click and call
  // window.showDirectoryPicker() (Chromium-only). Populate the popover's
  // nearby text input with the picked folder's name so the SPA's
  // existing "type a path" flow completes the workspace add.
  document.addEventListener('click', async (e) => {
    if (e.__folderShimHandled) return;
    let btn = e.target;
    while (btn && btn.tagName !== 'BUTTON' && btn !== document.body) btn = btn.parentElement;
    if (!btn || btn.tagName !== 'BUTTON') return;
    const txt = (btn.innerText || btn.textContent || '').trim().toLowerCase();
    if (!/add folder|select folder|browse|choose folder/.test(txt)) return;
    if (typeof window.showDirectoryPicker !== 'function') {
      console.warn('[folder-picker] showDirectoryPicker unavailable in this browser');
      return;
    }
    e.__folderShimHandled = true;
    e.preventDefault();
    e.stopImmediatePropagation();
    try {
      const dh = await window.showDirectoryPicker({mode:'read'});
      const name = dh.name;
      console.log('[folder-picker] user picked:', name);
      // Find the nearest visible text input inside the popover and populate it
      const popover = btn.closest('[role="dialog"],[role="menu"],[role="listbox"]') || document.body;
      const input = popover.querySelector('input[type="text"], input:not([type])') ||
                    document.querySelector('input[type="text"]:not([disabled])');
      if (input) {
        const proto = Object.getPrototypeOf(input);
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
        // Best-effort VM-side path — user can edit if needed
        const path = `/home/${(window.__user || '') || 'user'}/projects/${name}`;
        (setter || ((v)=>{input.value = v;})).call(input, path);
        input.dispatchEvent(new Event('input', {bubbles:true}));
        input.dispatchEvent(new Event('change', {bubbles:true}));
        input.focus();
        console.log('[folder-picker] populated input with', path);
      } else {
        // No input to populate — surface the name so the user can copy it.
        alert('Selected folder: ' + name + '. ' +
              'Note: the web hub cannot auto-map a browser-picked folder ' +
              'to a VM path. Type the target path into the popover manually, ' +
              'or use gcloud scp to upload.');
      }
    } catch (err) {
      if (err && err.name === 'AbortError') return; // user canceled
      console.error('[folder-picker] error:', err);
    }
  }, true);

  // 2) Watch chip for SPA-driven transitions. We only sync FROM chip TO state
  //    when a user click happened recently (within 5s); otherwise we treat
  //    localStorage as source-of-truth and force the chip to match. This
  //    prevents the SPA's initial-render chip reset from clobbering the
  //    persisted selection.
  let __lastChipLabel = null;
  function scanForModelLabel() {
    const chip = _findModelChip();
    if (!chip) { _forceChipLabel(window.__selectedModelLabel); return; }
    const txt = (chip.innerText || '').trim();
    if (!KNOWN_LABELS.includes(txt)) return;
    if (__lastChipLabel === null) {
      __lastChipLabel = txt;
      // On first sighting, if chip disagrees with stored pref, force chip
      // (don't let it clobber pref).
      if (txt !== window.__selectedModelLabel) _forceChipLabel(window.__selectedModelLabel);
      return;
    }
    if (__lastChipLabel !== txt) {
      __lastChipLabel = txt;
      if ((Date.now() - __userClickAt) < 5000) {
        // Post-click SPA update. Adopt or ignore depending on match.
        _setModel(txt, 'chip-transition');
      } else {
        // SPA changed chip on its own (initial render, cascade reply, etc.).
        // Ignore and force our pref back.
        if (txt !== window.__selectedModelLabel) _forceChipLabel(window.__selectedModelLabel);
      }
    } else if (txt !== window.__selectedModelLabel) {
      _forceChipLabel(window.__selectedModelLabel);
    }
  }
  const __modelPickerObserver = new MutationObserver(scanForModelLabel);
  document.addEventListener('DOMContentLoaded', () => {
    __modelPickerObserver.observe(document.body, { childList: true, subtree: true, characterData: true });
    scanForModelLabel();
    // Repeatedly force the chip during SPA hydration.
    for (const d of [200, 500, 1000, 2000, 4000]) {
      setTimeout(() => _forceChipLabel(window.__selectedModelLabel), d);
    }
  });

  // Wrap fetch to attach x-user-model on the cascade-related RPCs
  const RPC_NEEDS_LABEL = ['SendUserCascadeMessage', 'StartCascade',
                            'StreamAgentStateUpdates', 'GetSlashCommands',
                            'UpdateConversationAnnotations', 'GetTurnDiff'];
  const _origFetch = window.fetch.bind(window);
  window.fetch = function(input, init) {
    try {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      if (RPC_NEEDS_LABEL.some(r => url.includes(r))) {
        init = init || {};
        const h = new Headers(init.headers || (input && input.headers) || {});
        h.set('x-user-model', window.__selectedModelLabel || 'Gemini 3.5 Flash');
        init.headers = h;
      }
    } catch (e) { /* fall through */ }
    return _origFetch(input, init);
  };

  // Purge storage entries referencing conversation UUIDs that no longer exist
  // in the server's on-disk store. Stale cached IDs make the SPA abort with
  // "trajectory not found in any store" instead of issuing a clean StartCascade.
  // Runs synchronously (sync XHR) so the purge completes before the app boots.
  (function() {
    const uuidRegex = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

    let validIds = null;
    try {
      const xhr = new XMLHttpRequest();
      xhr.open("GET", "/valid-trajectories", false);  // synchronous on purpose
      xhr.send(null);
      if (xhr.status === 200) {
        validIds = new Set(JSON.parse(xhr.responseText).ids.map(s => s.toLowerCase()));
      }
    } catch (e) {
      console.error("Failed to fetch valid trajectory list, skipping purge:", e);
    }

    if (validIds === null) return;

    const purge = (storage, label) => {
      const doomed = [];
      try {
        for (let i = 0; i < storage.length; i++) {
          const key = storage.key(i);
          const val = storage.getItem(key) || "";
          const refs = ((key + " " + val).match(uuidRegex) || []).map(s => s.toLowerCase());
          if (refs.length > 0 && refs.some(id => !validIds.has(id))) {
            doomed.push(key);
          }
        }
        doomed.forEach(key => storage.removeItem(key));
        if (doomed.length > 0) {
          console.log("Purged stale trajectory references from " + label + ":", doomed);
        }
      } catch (e) {
        console.error("Failed to purge " + label + ":", e);
      }
    };

    purge(localStorage, "localStorage");
    purge(sessionStorage, "sessionStorage");
  })();
</script>
"""
        if "</head>" in html_text:
            html_text = html_text.replace("</head>", polyfill + "</head>", 1)
        elif "<head>" in html_text:
            html_text = html_text.replace("<head>", "<head>" + polyfill, 1)
        else:
            html_text = polyfill + html_text
            
        modified_content = html_text.encode("utf-8")
        if is_gzipped:
            import gzip
            modified_content = gzip.compress(modified_content)
            
        return Response(
            content=modified_content,
            status_code=resp.status_code,
            headers=resp_headers
        )

    # 3b. GetUserStatus augmentation — buffer the real language_server response
    # and append cascade_model_config_data so the SPA dropdown lists our models.
    # For proto responses: proto3 merges duplicate message-typed fields, so
    # appending an extra user_status field with only cmcd works.
    # For JSON responses: parse, add cascadeModelConfigData, re-serialize.
    if "GetUserStatus" in path or "getUserStatus" in path:
        # Force identity encoding upstream so we get plain bytes to augment.
        upstream_headers = {k: v for k, v in headers.items() if k.lower() != "accept-encoding"}
        upstream_headers["accept-encoding"] = "identity"
        # agy returns 0 bytes for a 0-byte request. If the SPA sent empty,
        # pad it with a minimal envelope so agy responds properly.
        if not body:
            ctype_l = (request.headers.get("content-type") or "").lower()
            if "grpc-web" in ctype_l or "connect+" in ctype_l or "grpc+" in ctype_l:
                body = b"\x00\x00\x00\x00\x02{}"
            else:
                body = b"{}"
        try:
            # Use a dedicated client — shared_client seems to lose response body
            async with httpx.AsyncClient(timeout=30.0) as _cli:
                us_resp = await _cli.post(
                    full_url, params=query_params, headers=upstream_headers, content=body
                )
        except httpx.HTTPError as exc:
            logger.error(f"Error forwarding GetUserStatus to backend: {exc}")
            return Response(content="Gateway Error", status_code=502)

        excluded = {"content-length", "transfer-encoding", "connection",
                    "keep-alive", "proxy-authenticate", "proxy-authorization",
                    "te", "trailers", "upgrade", "content-encoding"}
        rh = {k: v for k, v in us_resp.headers.items() if k.lower() not in excluded}
        rh["cache-control"] = "no-cache, no-store, must-revalidate"
        rh["set-cookie"] = f"csrfToken={os.environ.get('CSRF_TOKEN', '')}; Path=/; SameSite=Lax; Secure"

        raw = us_resp.content
        ctype = (us_resp.headers.get("content-type") or "").lower()
        logger.info(f"[GetUserStatus-DEBUG] req body_len={len(body) if body else 0} body_head={body[:60] if body else None!r} upstream status={us_resp.status_code} ct={ctype!r} raw_len={len(raw)} head={raw[:80]!r}")
        try:
            if us_resp.status_code == 200:
                # JSON (unary or grpc-web/connect enveloped JSON) — this is
                # what the SPA actually sends: `application/grpc-web+json`.
                if "json" in ctype:
                    is_enveloped_json = len(raw) >= 5 and raw[0] in (0x00,) and \
                        int.from_bytes(raw[1:5], "big") + 5 <= len(raw)
                    if is_enveloped_json:
                        plen = int.from_bytes(raw[1:5], "big")
                        payload = raw[5:5 + plen]
                        rest = raw[5 + plen:]
                    else:
                        payload = raw
                        rest = b""
                    doc = json.loads(payload.decode("utf-8"))
                    us_obj = doc.setdefault("userStatus", {})
                    if isinstance(us_obj, dict):
                        # REPLACE (not merge) so the language_server's
                        # "Custom Model: gemini-3.5-flash" placeholder entry
                        # doesn't ride along alongside our labels.
                        # Only include real proto fields on ClientModelConfig
                        # — protobuf-es v2 fromJson() throws on unknown fields
                        # (like "modelName"/"modelLabel"), which drops the whole
                        # response and renders "No models available".
                        # ClientModelConfig fields verified from binary:
                        #   1 label, 2 model_or_alias, 3 credit_multiplier,
                        #   4 disabled, 10 provider, 11 is_recommended,
                        #   13 pricing_type, 14 description, 18 supported_mime_types,
                        #   19 supports_thought_circulation.
                        # SPA reads the parsed JSON directly (no protobuf-es
                        # transform), so `modelOrAlias.choice.case === "model"`
                        # only works when we send the bufbuild discriminated-
                        # union runtime shape. Verified in headless Chrome.
                        def moa(enum_val):
                            return {"choice": {"case": "model", "value": enum_val}}
                        # The SPA's xOa() specifically searches clientModelSorts
                        # for a sort named "recommended" (case-insensitive) and
                        # takes .groups[0].options as the ONLY visible list.
                        # Without it, the dropdown renders "No models available"
                        # even when clientModelConfigs is populated.
                        us_obj["cascadeModelConfigData"] = {
                            "clientModelConfigs": [
                                {
                                    "label": label,
                                    "modelOrAlias": moa(enum_val),
                                    "disabled": False,
                                    "supportedMimeTypes": {},
                                    "supportsThoughtCirculation": False,
                                    "provider": "MODEL_PROVIDER_GOOGLE",
                                    "isRecommended": (enum_val == DEFAULT_MODEL_ENUM),
                                }
                                for label, enum_val in DROPDOWN_MODELS
                            ],
                            "clientModelSorts": [
                                {
                                    "name": "Recommended",
                                    "groups": [
                                        {
                                            "groupName": "",
                                            "modelLabels": [label for label, _ in DROPDOWN_MODELS],
                                        }
                                    ],
                                }
                            ],
                            "defaultOverrideModelConfig": {
                                "versionId": "1",
                                "modelOrAlias": moa(DEFAULT_MODEL_ENUM),
                            },
                        }
                    new_payload = json.dumps(doc).encode("utf-8")
                    if is_enveloped_json:
                        raw = b"\x00" + len(new_payload).to_bytes(4, "big") + new_payload + rest
                    else:
                        raw = new_payload
                    logger.info(f"Augmented GetUserStatus (JSON, enveloped={is_enveloped_json}) with {len(DROPDOWN_MODELS)} models")
                # Enveloped binary proto (Connect / gRPC-web)
                elif ("grpc-web+proto" in ctype or "grpc+proto" in ctype or "connect+proto" in ctype) \
                        and len(raw) >= 5 and raw[0] in (0x00,):
                    plen = int.from_bytes(raw[1:5], "big")
                    data_frame = raw[5:5 + plen]
                    rest = raw[5 + plen:]
                    new_data = data_frame + user_status_append()
                    new_header = b"\x00" + len(new_data).to_bytes(4, "big")
                    raw = new_header + new_data + rest
                    logger.info(f"Augmented GetUserStatus (enveloped proto) with {len(DROPDOWN_MODELS)} models")
                # Raw unary proto
                elif ctype == "application/proto" or ctype.startswith("application/proto;"):
                    raw = raw + user_status_append()
                    logger.info(f"Augmented GetUserStatus (raw proto) with {len(DROPDOWN_MODELS)} models")
                else:
                    logger.warning(f"GetUserStatus: no augmentation path for ct={ctype!r}")
        except Exception as e:
            logger.error(f"GetUserStatus augmentation failed: {e}", exc_info=True)

        return Response(content=raw, status_code=us_resp.status_code, headers=rh)

    # 3c. Race workaround for {StreamAgentStateUpdates, GetSlashCommands}.
    # The SPA generates the cascadeId client-side and fires both of these RPCs
    # BEFORE (or in parallel with) StartCascade. If the read RPC hits the server
    # first, the server returns "trajectory not found in any store" immediately
    # and the SPA aborts with "Agent execution terminated due to error". Absorb
    # the race here: if the conversation .db doesn't exist yet, wait up to ~6s.
    # Race-absorb disabled — was adding 20s delay without preventing errors
    # since agy's disk-write lag exceeds the wait. Softening handles not-found.
    RACY_PATHS = ()
    if any(p in path for p in RACY_PATHS) and body:
        try:
            # Extract cascadeId/conversationId from body — works for both raw
            # JSON and 5-byte-enveloped JSON, and the UUID_PATTERN just scans.
            payload_text = body.decode("utf-8", errors="ignore")
            m = UUID_PATTERN.search(payload_text)
            if m:
                convo_id = m.group(0).lower()
                # agy writes to antigravity-cli; hub writes to antigravity.
                # Wait for either.
                candidates = [
                    os.path.expanduser(f"~/.gemini/antigravity-cli/conversations/{convo_id}.db"),
                    os.path.expanduser(f"~/.gemini/antigravity/conversations/{convo_id}.db"),
                ]
                def _exists():
                    return any(os.path.exists(p) for p in candidates)
                if not _exists():
                    import asyncio
                    waited_ms = 0
                    for _ in range(200):  # 200 * 100ms = 20s
                        if _exists():
                            logger.info(f"{path.rsplit('/',1)[-1]} waited {waited_ms}ms for cascade {convo_id}")
                            break
                        await asyncio.sleep(0.1)
                        waited_ms += 100
                    else:
                        logger.warning(f"{path.rsplit('/',1)[-1]} timed out waiting for {convo_id}")
        except Exception as e:
            logger.error(f"Race-absorb pre-check failed: {e}")

    # 4. Handle Streaming & All other assets: stream unbuffered chunk-by-chunk with a dedicated client
    # to eliminate connection pooling multiplexing dropouts and HTTP/2 protocol errors.
    stream_client = httpx.AsyncClient(timeout=None)
    try:
        req = stream_client.build_request(
            method, full_url, params=query_params, headers=headers, content=body
        )
        resp = await stream_client.send(req, stream=True)
    except httpx.HTTPError as exc:
        logger.error(f"Error initiating backend stream to {url}: {exc}")
        await stream_client.aclose()
        return Response(content="Gateway Error: Unable to connect to backend", status_code=502)

    exclude_headers = {
        "content-length", "transfer-encoding",
        "connection", "keep-alive", "proxy-authenticate",
        "proxy-authorization", "te", "trailers", "upgrade"
    }
    resp_headers = {
        k: v for k, v in resp.headers.items() if k.lower() not in exclude_headers
    }
    resp_headers["cache-control"] = "no-cache, no-store, must-revalidate"
    resp_headers["pragma"] = "no-cache"
    resp_headers["expires"] = "0"
    resp_headers["set-cookie"] = f"csrfToken={os.environ.get('CSRF_TOKEN', '')}; Path=/; SameSite=Lax; Secure"
    resp_headers["X-Accel-Buffering"] = "no"

    # "Trajectory not found" softening for the three RPCs the SPA fires on
    # page load for its client-generated placeholder cascadeIds — before
    # StartCascade has ever run. If we detect that error in the first frame,
    # swap in a benign empty-idle response so the console doesn't fill with
    # scary red errors for what's really a "no such conversation, that's OK"
    # situation.
    SOFTEN_PATHS = (
        "GetSlashCommands",
        "UpdateConversationAnnotations",
    )
    should_soften = any(p in path for p in SOFTEN_PATHS)

    if should_soften:
        import asyncio
        peek_chunks = []
        raw_iter = resp.aiter_raw().__aiter__()
        # Buffer chunks up to 4KB / 2s to reliably detect not-found error text
        # (httpx may return an initial empty chunk before real payload).
        async def _peek():
            async for c in raw_iter:
                peek_chunks.append(c)
                if sum(len(x) for x in peek_chunks) >= 4096:
                    return
        try:
            await asyncio.wait_for(_peek(), timeout=2.0)
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(f"soften peek error {path}: {e}")
        peek = b"".join(peek_chunks)
        # gRPC-Web reports errors in HEADERS via grpc-status/grpc-message,
        # NOT in the body. Detect not-found either way.
        grpc_msg = resp.headers.get("grpc-message", "")
        grpc_status = resp.headers.get("grpc-status", "0")
        is_not_found = (
            b"not found in any store" in peek
            or b"not found on disk" in peek
            or "not found in any store" in grpc_msg
            or "not found on disk" in grpc_msg
        )

        if is_not_found:
            m = UUID_PATTERN.search(body.decode("utf-8", errors="ignore") if body else "")
            convo_id = m.group(0) if m else "00000000-0000-0000-0000-000000000000"
            ctype_l = (resp.headers.get("content-type") or "").lower()
            enveloped = "grpc-web" in ctype_l or "connect+" in ctype_l or "grpc+" in ctype_l

            if "StreamAgentStateUpdates" in path:
                # Close bad attempt, retry every 500ms until agy has the cascade,
                # then stream through. Emit an initial idle frame to keep the
                # SPA connection alive while we retry.
                import asyncio
                await resp.aclose(); await stream_client.aclose()
                logger.info(f"stream-retry: waiting for agy to know {convo_id}")
                async def stream_retry():  # unused — kept for reference
                    for attempt in range(60):
                        await asyncio.sleep(0.5)
                        cli = httpx.AsyncClient(timeout=None)
                        try:
                            r = await cli.send(
                                cli.build_request("POST", full_url,
                                                  headers=dict(headers), content=body),
                                stream=True,
                            )
                            grpc_status = r.headers.get("grpc-status", "0")
                            grpc_msg = r.headers.get("grpc-message", "")
                            if grpc_status in ("0", None, "") and "not found" not in grpc_msg:
                                async for chunk in r.aiter_raw():
                                    yield chunk
                                await r.aclose(); await cli.aclose()
                                return
                            await r.aclose(); await cli.aclose()
                        except Exception as e:
                            logger.error(f"stream-retry err {convo_id}: {e}")
                            await cli.aclose()
                    logger.warning(f"stream-retry: {convo_id} still not found after 30s")
                    # Fallback: idle
                    idle = b'{"update":{"conversationId":"' + convo_id.encode() + b'","status":"CASCADE_RUN_STATUS_IDLE"}}'
                    if enveloped:
                        yield b"\x00" + len(idle).to_bytes(4, "big") + idle
                    while True:
                        await asyncio.sleep(60)
                return StreamingResponse(
                    stream_retry(), status_code=200,
                    headers={"content-type": ctype_l or "application/grpc-web+json",
                             "X-Accel-Buffering": "no", "cache-control": "no-cache"},
                )
            elif False:
                # DON'T fake an idle response — that makes the SPA think the
                # cascade completed empty. Instead: close the current attempt
                # and RETRY agy every 300ms until it returns real data
                # (SendUserCascadeMessage will register the cascade shortly).
                # Then passthrough that stream.
                import asyncio
                await resp.aclose(); await stream_client.aclose()
                logger.info(f"soften-retry: waiting for agy to have {convo_id}")

                async def retry_and_stream():
                    for attempt in range(60):  # 60 * 300ms = 18s total
                        await asyncio.sleep(0.3)
                        cli = httpx.AsyncClient(timeout=None)
                        try:
                            r = await cli.post(
                                full_url,
                                headers={k: v for k, v in headers.items()},
                                content=body,
                            )
                            raw = r.content
                            # Still not-found? keep waiting.
                            if b"not found in any store" in raw or b"not found on disk" in raw or not raw:
                                await cli.aclose()
                                continue
                            # Got real data! stream it back
                            logger.info(f"soften-retry: got real state for {convo_id} after {(attempt+1)*300}ms")
                            yield raw
                            await cli.aclose()
                            # Re-subscribe to get future updates
                            cli2 = httpx.AsyncClient(timeout=None)
                            try:
                                async with cli2.stream(
                                    "POST", full_url,
                                    headers={k: v for k, v in headers.items()},
                                    content=body,
                                ) as r2:
                                    async for chunk in r2.aiter_raw():
                                        yield chunk
                            finally:
                                await cli2.aclose()
                            return
                        except Exception as e:
                            logger.error(f"soften-retry attempt {attempt} error: {e}")
                            await cli.aclose()
                    # Fallback after 18s: send idle so SPA doesn't hang
                    import json as _j
                    idle = _j.dumps({"update": {"conversationId": convo_id,
                        "status": "CASCADE_RUN_STATUS_IDLE",
                        "executableStatus": "CASCADE_RUN_STATUS_IDLE",
                        "executorLoopStatus": "CASCADE_RUN_STATUS_IDLE",
                    }}).encode()
                    if enveloped:
                        yield b"\x00" + len(idle).to_bytes(4, "big") + idle
                    else:
                        yield idle
                    while True:
                        await asyncio.sleep(60)

                return StreamingResponse(
                    retry_and_stream(), status_code=200,
                    headers={"content-type": ctype_l or "application/grpc-web+json",
                             "X-Accel-Buffering": "no", "cache-control": "no-cache"},
                )
            else:
                # Unary — return an empty success (with grpc-web trailer if needed)
                data = b"{}"
                if enveloped:
                    data_frame = b"\x00" + len(data).to_bytes(4, "big") + data
                    trailer = b"grpc-status: 0\r\n"
                    trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
                    body_out = data_frame + trailer_frame
                    rct = "application/grpc-web+json"
                else:
                    body_out = data
                    rct = "application/json"
                await resp.aclose(); await stream_client.aclose()
                logger.info(f"softened not-found → empty {path.rsplit('/',1)[-1]} for {convo_id}")
                return Response(content=body_out, status_code=200,
                                headers={"content-type": rct})

        # Not the "not found" case — pass through, yielding the peeked chunk
        # first then continuing to read from the SAME iterator.
        async def passthrough_gen():
            try:
                if peek:
                    yield peek
                async for chunk in raw_iter:
                    yield chunk
            finally:
                await resp.aclose()
                await stream_client.aclose()
        return StreamingResponse(
            passthrough_gen(),
            status_code=resp.status_code,
            headers=resp_headers,
        )

    async def stream_generator():
        try:
            async for chunk in resp.aiter_raw():
                yield chunk
        finally:
            await resp.aclose()
            await stream_client.aclose()

    return StreamingResponse(
        stream_generator(),
        status_code=resp.status_code,
        headers=resp_headers,
    )

if __name__ == "__main__":
    _load_cascades_from_disk()
    uvicorn.run(app, host="127.0.0.1", port=8082, log_level="info")
