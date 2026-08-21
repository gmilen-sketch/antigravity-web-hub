import sys
import http.server
import socketserver
import json
import logging
import os
import urllib.request
import urllib.error
import subprocess
import time
import re
import socket
import threading

_server_ready = threading.Event()
_server_ready.set()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "firsttestproject-343414")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")

_token_cache = {"token": "", "expires_at": 0}

_cascade_events = {}
_cascade_events_lock = threading.Lock()

def get_cascade_event(cascade_id):
    if not cascade_id:
        return None
    with _cascade_events_lock:
        if cascade_id not in _cascade_events:
            evt = threading.Event()
            # Initialize with event set so requests do not block by default.
            # StartCascade will clear this event to block concurrent requests while it aligns the database.
            evt.set()
            _cascade_events[cascade_id] = evt
        return _cascade_events[cascade_id]

def extract_cascade_id(body: bytes, is_json: bool) -> str:
    cascade_id = None
    try:
        if is_json:
            is_env_json = len(body) >= 5 and body[0] in (0x00, 0x80)
            payload = body[5:5+int.from_bytes(body[1:5], "big")] if is_env_json else body
            doc = json.loads(payload.decode("utf-8"))
            cascade_id = doc.get("cascadeId") or doc.get("cascade_id") or doc.get("conversationId") or doc.get("conversation_id")
    except Exception as ex:
        pass
        
    if not cascade_id:
        # Fallback to regex pattern matching on raw body
        try:
            m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", body.decode("utf-8", errors="ignore"), re.IGNORECASE)
            if m:
                cascade_id = m.group(0)
        except Exception as ex:
            pass
    return cascade_id

def get_adc_token(force: bool = False) -> str:
    """Fetches and caches fresh GCP OAuth access token via gcloud / ADC or GCE metadata server."""
    now = time.time()
    if not force and now < _token_cache["expires_at"] and _token_cache["token"]:
        return _token_cache["token"]

    # 1. Primary: gcloud auth print-access-token / application-default (guarantees cloud-platform scope)
    for cmd in [
        ["gcloud", "auth", "print-access-token"],
        ["gcloud", "auth", "application-default", "print-access-token"],
    ]:
        try:
            env = dict(os.environ)
            env["CLOUDSDK_CONTEXT_AWARE_ACCESS_DISABLE_ECP"] = "true"
            token = subprocess.check_output(cmd, text=True, env=env, stderr=subprocess.DEVNULL).strip()
            if token and not token.startswith("ERROR"):
                _token_cache["token"] = token
                _token_cache["expires_at"] = now + 3000
                logging.info(f"Fetched fresh token via {' '.join(cmd)} for Vertex AI bridge.")
                return token
        except Exception as e:
            logging.debug(f"Command {' '.join(cmd)} failed: {e}")

    # 2. Fallback: GCE metadata server
    try:
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"}
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            token = data.get("access_token")
            if token:
                _token_cache["token"] = token
                _token_cache["expires_at"] = now + 3000
                logging.info("Fetched GCE metadata service account token for Vertex AI bridge.")
                return token
    except Exception as ex:
        logging.warning(f"Could not fetch GCE metadata token: {ex}")

    return ""



def read_request_body(handler) -> bytes:
    """Safely reads request body supporting Content-Length and Transfer-Encoding: chunked."""
    transfer_encoding = handler.headers.get("Transfer-Encoding", "").lower()
    if "chunked" in transfer_encoding:
        body = bytearray()
        while True:
            line = handler.rfile.readline().strip()
            if not line:
                break
            try:
                chunk_size = int(line.split(b";")[0], 16)
            except ValueError:
                logging.error(f"Invalid chunk size hex: {line}")
                break
            if chunk_size == 0:
                handler.rfile.readline()  # consume trailing \r\n
                break
            chunk_data = handler.rfile.read(chunk_size)
            body.extend(chunk_data)
            handler.rfile.readline()  # consume trailing \r\n
        return bytes(body)
    else:
        content_len = int(handler.headers.get("Content-Length", 0))
        return handler.rfile.read(content_len) if content_len > 0 else b""

def map_model_name(requested_model_from_payload):
    if not requested_model_from_payload:
        return "gemini-3.7-flash"
    req_str = str(requested_model_from_payload)
    req_lower = req_str.lower()
    
    # 1. Claude Fable / Haiku (enum 340, 1272)
    if "340" in req_str or "1272" in req_str or "haiku" in req_lower or "fable" in req_lower:
        return "claude-fable-5"
        
    # 2. Claude Opus (enum 290, 291, 1279)
    if "290" in req_str or "291" in req_str or "1279" in req_str or "opus" in req_lower:
        if "4.7" in req_lower:
            return "claude-opus-4-7"
        return "claude-opus-5"
        
    # 3. Claude Sonnet (enum 333, 334, 281, 282)
    if "333" in req_str or "334" in req_str or "281" in req_str or "282" in req_str or "claude" in req_lower or "sonnet" in req_lower:
        if "3.5" in req_lower or "281" in req_str:
            return "claude-3-5-sonnet-v2@20241022"
        return "claude-3-7-sonnet@20250219"
        
    # 4. Gemini 3.7 Flash (enum 352, 353, 1003, 1004)
    if "352" in req_str or "353" in req_str or "3.7" in req_lower:
        return "gemini-3.7-flash"
        
    # 5. Gemini 3.6 Flash (enum 350, 1001)
    if "350" in req_str or "1001" in req_str or "3.6" in req_lower:
        return "gemini-3.6-flash"
        
    # 6. Gemini 3.5 Flash Lite (enum 330, 344)
    if "330" in req_str or "344" in req_str or "lite" in req_lower or "light" in req_lower:
        return "gemini-3.5-flash-lite"
        
    # 7. Gemini 3.5 Pro (enum 246, 326, 331, 327)
    if "246" in req_str or "326" in req_str or "331" in req_str or "pro" in req_lower:
        return "gemini-3.5-pro"
        
    # 8. Gemini 3.5 Flash (enum 348, 1000)
    if "348" in req_str or "1000" in req_str or "3.5" in req_lower:
        return "gemini-3.5-flash"
        
    return "gemini-3.7-flash"

PORT = 8083

DEFAULT_MODEL_ENUM = 352
DEFAULT_MODEL_NAME = "MODEL_GOOGLE_GEMINI_RIFTRUNNER_THINKING_LOW"

DROPDOWN_MODELS = [
    ("Gemini 3.7 Flash",              352),  # MODEL_GOOGLE_GEMINI_RIFTRUNNER_THINKING_LOW
    ("Gemini 3.6 Flash",              350),  # MODEL_GOOGLE_GEMINI_INFINITYJET
    ("Gemini 3.5 Flash Lite",         330),  # MODEL_GOOGLE_GEMINI_2_5_FLASH_LITE
    ("Claude 3.7 Sonnet (Vertex AI)", 333),  # MODEL_CLAUDE_4_5_SONNET
    ("Claude Opus 5 (Vertex AI)",     290),  # MODEL_CLAUDE_4_OPUS
    ("Claude Fable 5 (Next-Gen)",     340),  # MODEL_CLAUDE_4_5_HAIKU
]

GEMINI_SUPPORTED_MIME_TYPES = {
    "image/png": True,
    "image/jpeg": True,
    "image/webp": True,
    "image/heic": True,
    "image/heif": True,
    "image/gif": True,
    "application/pdf": True,
    "video/webm": True,
    "video/mp4": True,
    "text/plain": True,
    "text/html": True,
    "text/css": True,
    "text/javascript": True,
    "application/x-javascript": True,
    "text/x-typescript": True,
    "application/x-typescript": True,
    "text/csv": True,
    "text/markdown": True,
    "text/x-python": True,
    "text/x-python-script": True,
    "application/x-python-code": True,
    "application/json": True,
    "application/x-ipynb+json": True,
    "text/xml": True,
    "application/rtf": True,
    "text/rtf": True,
    "video/audio/wav": True,
    "audio/webm;codecs=opus": True,
}

def moa(val):
    return {
        "model": val,
        "choice": {"case": "model", "value": val}
    }

def build_cascade_model_config_data():
    return {
        "clientModelConfigs": [
            {
                "label": label,
                "modelOrAlias": moa(val),
                "disabled": False,
                "supportedMimeTypes": GEMINI_SUPPORTED_MIME_TYPES,
                "supportsThoughtCirculation": False,
                "provider": "MODEL_PROVIDER_GOOGLE",
                "isRecommended": (val == DEFAULT_MODEL_ENUM),
            }
            for label, val in DROPDOWN_MODELS
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


def _is_unset_enum(v):
    if v is None or v == 0 or v == "" or v == "MODEL_UNSPECIFIED":
        return True
    if isinstance(v, dict):
        choice = v.get("choice", {})
        if isinstance(choice, dict):
            inner = choice.get("value")
            return inner is None or inner == 0 or inner == "" or inner == "MODEL_UNSPECIFIED"
        m = v.get("model", v.get("value"))
        return m is None or m == 0 or m == "" or m == "MODEL_UNSPECIFIED"
    return False

def forward_request(path, method, headers, body):
    _server_ready.wait(timeout=12.0)
    url = f"http://127.0.0.1:8081{path}"
    fw_headers = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in ("host", "content-length", "connection", "accept-encoding"):
            continue
        fw_headers[k] = v
    fw_headers["Host"] = "127.0.0.1:8081"
    fw_headers["Accept-Encoding"] = "identity"
    
    req = urllib.request.Request(url, data=body, headers=fw_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            resp_headers = {k: v for k, v in response.info().items()}
            resp_body = response.read()
            return response.status, resp_headers, resp_body
    except urllib.error.HTTPError as e:
        resp_headers = {k: v for k, v in e.info().items()}
        resp_body = e.read()
        return e.code, resp_headers, resp_body
    except Exception as e:
        logging.error(f"Error forwarding request to {url}: {e}")
        return 502, {}, b"Gateway Error"

def get_active_ui_model():
    pbtxt_path = os.path.expanduser("~/.gemini/antigravity/jetski_state.pbtxt")
    if os.path.exists(pbtxt_path):
        try:
            with open(pbtxt_path, "r") as f:
                content = f.read()
                m = re.search(r"last_selected_agent_model:\s*(\w+)", content)
                if m:
                    model_str = m.group(1).strip()
                    if model_str and model_str != "MODEL_UNSPECIFIED":
                        mapped = map_model_name(model_str)
                        return mapped
        except Exception as e:
            logging.error(f"Error reading jetski_state.pbtxt: {e}")
    return None

def get_active_ui_model_enum():
    pbtxt_path = os.path.expanduser("~/.gemini/antigravity/jetski_state.pbtxt")
    if os.path.exists(pbtxt_path):
        try:
            with open(pbtxt_path, "r") as f:
                content = f.read()
                m = re.search(r"last_selected_agent_model:\s*(\w+)", content)
                if m:
                    model_str = m.group(1).strip()
                    if model_str and model_str != "MODEL_UNSPECIFIED":
                        enum_map = {
                            "MODEL_CLAUDE_4_OPUS": 290,
                            "MODEL_CLAUDE_4_5_SONNET": 333,
                            "MODEL_CLAUDE_4_5_HAIKU": 340,
                            "MODEL_GOOGLE_GEMINI_INFINITYJET": 350,
                            "MODEL_GOOGLE_GEMINI_RIFTRUNNER_THINKING_LOW": 352,
                            "MODEL_GOOGLE_GEMINI_2_5_FLASH_LITE": 330,
                            "MODEL_GOOGLE_GEMINI_2_5_FLASH": 312
                        }
                        if model_str in enum_map:
                            return enum_map[model_str]
                        return model_str
        except Exception as e:
            logging.error(f"Error reading jetski_state.pbtxt: {e}")
    return None

def extract_requested_model(doc):
    # 1. Check active UI model from jetski_state.pbtxt first
    ui_enum = get_active_ui_model_enum()
    if ui_enum is not None:
        return ui_enum

    # 2. Check top-level requestedModel
    req_m = doc.get("requestedModel") or doc.get("requested_model")
    if req_m is not None and not _is_unset_enum(req_m):
        if isinstance(req_m, dict):
            choice = req_m.get("choice", {})
            if isinstance(choice, dict) and choice.get("value") not in (None, 0, "", "MODEL_UNSPECIFIED"):
                return choice.get("value")
            val = req_m.get("model") or req_m.get("value")
            if val not in (None, 0, "", "MODEL_UNSPECIFIED"):
                return val
        elif req_m not in (0, "", "MODEL_UNSPECIFIED"):
            return req_m
            
    # 3. Check cascadeConfig.plannerConfig.requestedModel
    cc = doc.get("cascadeConfig") or doc.get("cascade_config") or {}
    if isinstance(cc, dict):
        pc = cc.get("plannerConfig") or cc.get("planner_config") or {}
        if isinstance(pc, dict):
            rm = pc.get("requestedModel") or pc.get("requested_model")
            if rm is not None and not _is_unset_enum(rm):
                if isinstance(rm, dict):
                    choice = rm.get("choice", {})
                    if isinstance(choice, dict) and choice.get("value") not in (None, 0, "", "MODEL_UNSPECIFIED"):
                        return choice.get("value")
                    val = rm.get("model") or rm.get("value")
                    if val not in (None, 0, "", "MODEL_UNSPECIFIED"):
                        return val
                elif rm not in (0, "", "MODEL_UNSPECIFIED"):
                    return rm
            pm = pc.get("planModel") or pc.get("plan_model")
            if pm not in (None, 0, "", "MODEL_UNSPECIFIED"):
                return pm
    return None

def inject_model_into_json_doc(doc, is_start_cascade=False):
    modified = False

    extracted_model = extract_requested_model(doc)
    model_to_use = extracted_model if extracted_model is not None else DEFAULT_MODEL_ENUM
    if isinstance(model_to_use, str) and model_to_use.isdigit():
        model_to_use = int(model_to_use)
    logging.info(f"inject_model_into_json_doc (is_start_cascade={is_start_cascade}): extracted={extracted_model} -> using={model_to_use}")

    # 1. Normalize top-level requestedModel
    if "requested_model" in doc:
        del doc["requested_model"]
        modified = True

    if is_start_cascade:
        # StartCascadeRequest.requested_model (field 14) is codeium_common_pb.Model ENUM, NOT a message dict!
        doc["requestedModel"] = model_to_use
        modified = True
    else:
        # SendUserCascadeMessage does not have a top-level requestedModel field in protobuf
        if "requestedModel" in doc:
            del doc["requestedModel"]
            modified = True

    # 2. Normalize cascadeConfig / cascade_config
    cascade_cfg = doc.get("cascadeConfig") or doc.get("cascade_config")
    if "cascade_config" in doc:
        del doc["cascade_config"]
        modified = True

    if cascade_cfg is None:
        doc["cascadeConfig"] = {}
        cascade_cfg = doc["cascadeConfig"]
        modified = True
    else:
        doc["cascadeConfig"] = cascade_cfg

    if isinstance(cascade_cfg, dict):
        # 3. Normalize plannerConfig / planner_config
        planner_cfg = cascade_cfg.get("plannerConfig") or cascade_cfg.get("planner_config")
        if "planner_config" in cascade_cfg:
            del cascade_cfg["planner_config"]
            modified = True

        if planner_cfg is None:
            cascade_cfg["plannerConfig"] = {}
            planner_cfg = cascade_cfg["plannerConfig"]
            modified = True
        else:
            cascade_cfg["plannerConfig"] = planner_cfg

        if isinstance(planner_cfg, dict):
            # 4. Normalize planModel / plan_model
            if "plan_model" in planner_cfg:
                del planner_cfg["plan_model"]
                modified = True

            planner_cfg["planModel"] = model_to_use
            modified = True

            # 5. Normalize requestedModel / requested_model
            if "requested_model" in planner_cfg:
                del planner_cfg["requested_model"]
                modified = True

            planner_cfg["requestedModel"] = moa(model_to_use)
            modified = True

            # Normalize conversational agenticMode
            conv = planner_cfg.get("conversational")
            if isinstance(conv, dict) and conv.get("agenticMode"):
                conv["agenticMode"] = False
                modified = True

        # 6. Normalize executorConfig / executor_config
        executor_cfg = cascade_cfg.get("executorConfig") or cascade_cfg.get("executor_config")
        if "executor_config" in cascade_cfg:
            del cascade_cfg["executor_config"]
            modified = True

        if executor_cfg is None:
            cascade_cfg["executorConfig"] = {}
            executor_cfg = cascade_cfg["executorConfig"]
            modified = True
        else:
            cascade_cfg["executorConfig"] = executor_cfg

        if isinstance(executor_cfg, dict):
            if not executor_cfg.get("disableEmptyOutputContinuation"):
                executor_cfg["disableEmptyOutputContinuation"] = True
                modified = True

    return modified

def restart_language_server_and_wait():
    _server_ready.clear()
    logging.info("Killing language_server synchronously...")
    try:
        subprocess.run(["pkill", "-f", "language_server"])
    except Exception as e:
        logging.error(f"Failed to kill language_server: {e}")
    
    start_time = time.time()
    timeout = 10.0
    
    # Give start_hub.sh a moment to recognize the process died and restart it
    time.sleep(0.3)
    
    logging.info("Waiting for language_server to come back online on port 8081...")
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                s.connect(("127.0.0.1", 8081))
                logging.info(f"language_server is back online after {time.time() - start_time:.2f} seconds.")
                _server_ready.set()
                return True
        except Exception:
            time.sleep(0.1)
            
    logging.warning("Timeout waiting for language_server to restart and listen on port 8081.")
    _server_ready.set()
    return False

class CCPAHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logging.info("%s - - %s" % (self.address_string(), format%args))

    def forward_and_stream(self, path, method, headers, body):
        _server_ready.wait(timeout=12.0)
        url = f"http://127.0.0.1:8081{path}"
        fw_headers = {}
        for k, v in headers.items():
            lk = k.lower()
            if lk in ("host", "content-length", "connection", "accept-encoding"):
                continue
            fw_headers[k] = v
        fw_headers["Host"] = "127.0.0.1:8081"
        fw_headers["Accept-Encoding"] = "identity"
        
        req = urllib.request.Request(url, data=body, headers=fw_headers, method=method)
        # Use longer timeout for state streaming to avoid network/gateway errors
        timeout = 1800 if "StreamAgentStateUpdates" in path or "streamAgentStateUpdates" in path else 120
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                self.send_response(response.status)
                
                # Check if the upstream response is chunked or lacks a Content-Length
                is_chunked = False
                transfer_enc = response.info().get("Transfer-Encoding", "").lower()
                if "chunked" in transfer_enc or not response.info().get("Content-Length"):
                    is_chunked = True
                
                for k, v in response.info().items():
                    if k.lower() not in ("content-length", "transfer-encoding"):
                        self.send_header(k, v)
                
                if is_chunked:
                    self.send_header("Transfer-Encoding", "chunked")
                else:
                    cl = response.info().get("Content-Length")
                    if cl:
                        self.send_header("Content-Length", cl)
                
                self.end_headers()
                
                while True:
                    chunk = response.read1(4096)
                    if not chunk:
                        break
                    
                    if is_chunked:
                        # Write chunk in standard HTTP/1.1 chunked format: <hex_size>\r\n<data>\r\n
                        self.wfile.write(f"{len(chunk):x}\r\n".encode('ascii'))
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                    else:
                        self.wfile.write(chunk)
                    self.wfile.flush()
                
                if is_chunked:
                    # Write terminating chunk
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.info().items():
                if k.lower() not in ("content-length", "transfer-encoding"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            logging.error(f"Error forwarding request to {url}: {e}")
            self.send_response(502)
            self.end_headers()
            self.wfile.write(b"Gateway Error")

    def do_POST(self):
        post_data = read_request_body(self)
        
        logging.info(f"--- RECEIVED POST ---")
        logging.info(f"Path: {self.path}")
        
        ctype_raw = self.headers.get("Content-Type", "").lower()
        ctype = ctype_raw.split(";", 1)[0].strip()
        
        enveloped_types = {
            "application/connect+proto",
            "application/grpc-web+proto",
            "application/grpc-web",
            "application/grpc+proto",
            "application/grpc",
        }
        raw_proto_types = {"application/proto"}
        
        is_enveloped = ctype in enveloped_types and "json" not in ctype
        is_raw_proto = ctype in raw_proto_types and "json" not in ctype
        is_json = "json" in ctype
        
        if "/a2a/app" in self.path or "/a2a" in self.path:
            logging.info(f"--- A2A REQUEST RECEIVED ---")
            try:
                doc = json.loads(post_data.decode("utf-8")) if post_data else {}
                logging.info(f"A2A Payload: {json.dumps(doc, indent=2)}")
                req_id = doc.get("id", 1)
                params = doc.get("params", {})
                user_msg = ""
                if isinstance(params, dict):
                    msg_obj = params.get("message", {})
                    if isinstance(msg_obj, dict):
                        user_msg = msg_obj.get("text", "")
                    elif isinstance(msg_obj, str):
                        user_msg = msg_obj
                    if not user_msg:
                        user_msg = params.get("text", "")
                
                # Execute environment command based on user query
                msg_lower = user_msg.lower()
                if any(w in msg_lower for w in ["virtual machine", "vm", "instances", "compute"]):
                    try:
                        res = subprocess.check_output(
                            ["gcloud", "compute", "instances", "list", "--project=firsttestproject-343414"],
                            stderr=subprocess.STDOUT
                        ).decode("utf-8")
                        output_text = f"Here are the active virtual machines in project `firsttestproject-343414`:\n\n```text\n{res}\n```\n\nConnected to Antigravity Cloud Sandbox: https://antigravity.customertests.info/."
                    except Exception as ex:
                        output_text = f"Error executing gcloud compute instances list: {ex}"
                elif any(w in msg_lower for w in ["dataset", "bigquery", "tables"]):
                    try:
                        res = subprocess.check_output(
                            ["bq", "ls", "--project_id=firsttestproject-343414"],
                            stderr=subprocess.STDOUT
                        ).decode("utf-8")
                        output_text = f"Here are the BigQuery datasets in `firsttestproject-343414`:\n\n```text\n{res}\n```"
                    except Exception as ex:
                        output_text = f"Error querying BigQuery: {ex}"
                else:
                    output_text = f"Antigravity Coding Agent received your request:\n> {user_msg}\n\nWorkspace active with Monaco editor and terminal at: https://antigravity.customertests.info/."
                
                resp_payload = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "status": "COMPLETED",
                        "message": {
                            "role": "assistant",
                            "parts": [
                                {
                                    "text": output_text
                                }
                            ]
                        }
                    }
                }
                resp_bytes = json.dumps(resp_payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)
                return
            except Exception as e:
                logging.error(f"Error processing A2A request: {e}")
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32603, "message": str(e)}
                }
                err_bytes = json.dumps(err_resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_bytes)))
                self.end_headers()
                self.wfile.write(err_bytes)
                return

        if "streamGenerateContent" in self.path:
            logging.info(f"--- STREAM GENERATE CONTENT INTERCEPTED ---")
            
            token = get_adc_token()
            if not token:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"No ADC Token Available")
                return

            payload_bytes = post_data
            is_anthropic = False
            try:
                doc = json.loads(post_data.decode("utf-8"))
                logging.info(f"Payload: {json.dumps(doc, indent=2)}")
                with open("/tmp/stream_req.json", "w") as f:
                    json.dump(doc, f, indent=2)
                
                # Check active UI selected model first from jetski_state.pbtxt
                active_ui_model = get_active_ui_model()
                if active_ui_model:
                    model = active_ui_model
                    logging.info(f"Using model selected from active UI: {model}")
                else:
                    model = "gemini-3.7-flash"
                    req_model = doc.get("model") or doc.get("modelName") or doc.get("model_name")
                    if req_model:
                        model = map_model_name(req_model)
                
                if model.startswith("claude-"):
                    is_anthropic = True
                    # Translate Gemini payload to Anthropic Messages payload
                    inner_req = doc.get("request", doc)
                    system_prompt = ""
                    if "systemInstruction" in inner_req:
                        parts = inner_req["systemInstruction"].get("parts", [])
                        system_prompt = " ".join([p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p])
                    
                    anthropic_messages = []
                    for c in inner_req.get("contents", []):
                        role = "assistant" if c.get("role") == "model" else "user"
                        content_blocks = []
                        for p in c.get("parts", []):
                            if isinstance(p, dict) and "text" in p and p["text"]:
                                content_blocks.append({"type": "text", "text": p["text"]})
                        if content_blocks:
                            anthropic_messages.append({"role": role, "content": content_blocks})
                    
                    # Ensure at least one user message
                    if not anthropic_messages:
                        anthropic_messages = [{"role": "user", "content": [{"type": "text", "text": "Hello"}]}]
                        
                    anthropic_payload = {
                        "anthropic_version": "vertex-2023-10-16",
                        "max_tokens": 8192,
                        "stream": True,
                        "messages": anthropic_messages
                    }
                    if system_prompt:
                        anthropic_payload["system"] = system_prompt
                        
                    payload_bytes = json.dumps(anthropic_payload).encode("utf-8")
                    logging.info(f"Forwarding Anthropic Messages payload for model: {model}")
                else:
                    # Enforce standard Gemini API payload format for Vertex AI
                    if "request" in doc:
                        inner_req = doc["request"]
                        allowed_keys = {
                            "contents",
                            "systemInstruction",
                            "tools",
                            "toolConfig",
                            "generationConfig",
                            "safetySettings",
                        }
                        cleaned_req = {k: v for k, v in inner_req.items() if k in allowed_keys}
                        
                        # Prevent thinkingConfig compatibility issues for disabled thinking or non-reasoning models
                        if "generationConfig" in cleaned_req:
                            gen_cfg = cleaned_req["generationConfig"]
                            if isinstance(gen_cfg, dict) and "thinkingConfig" in gen_cfg:
                                tc = gen_cfg["thinkingConfig"]
                                if not isinstance(tc, dict) or tc.get("thinkingBudget", 0) == 0 or "3.7" not in model:
                                    del gen_cfg["thinkingConfig"]
                        
                        payload_bytes = json.dumps(cleaned_req).encode("utf-8")
                        logging.info(f"Forwarding cleaned standard payload for Vertex AI ({model}).")
            except Exception as e:
                logging.error(f"Failed to parse and clean streamGenerateContent payload: {e}")

            if is_anthropic:
                anthropic_location = "global"
                vertex_url = f"https://aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/global/publishers/anthropic/models/{model}:streamRawPredict"
            else:
                # Use v1beta1 REST endpoint with 'global' location as verified working
                vertex_url = f"https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/global/publishers/google/models/{model}:streamGenerateContent?alt=sse"
                
            logging.info(f"Forwarding stream to Vertex AI: {vertex_url}")
            
            max_retries = 5
            backoff_base = 1.0
            attempt = 0
            resp = None

            while attempt < max_retries:
                attempt += 1
                try:
                    req = urllib.request.Request(
                        vertex_url,
                        data=payload_bytes,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        method="POST",
                    )
                    resp = urllib.request.urlopen(req)
                    break
                except urllib.error.HTTPError as he:
                    if he.code in (401, 403, 429, 500, 502, 503, 504) and attempt < max_retries:
                        sleep_time = backoff_base * (2 ** (attempt - 1))
                        logging.warning(f"Vertex AI stream request returned HTTP {he.code}. Retrying in {sleep_time:.2f}s (attempt {attempt}/{max_retries})...")
                        time.sleep(sleep_time)
                        token = get_adc_token(force=True)
                    else:
                        logging.error(f"Vertex AI stream HTTPError: {he.code} {he.reason}")
                        try:
                            err_body = he.read().decode('utf-8', errors='ignore')
                            logging.error(f"Vertex AI error body: {err_body}")
                        except Exception:
                            pass
                        raise he
                except Exception as ex:
                    if attempt < max_retries:
                        sleep_time = backoff_base * (2 ** (attempt - 1))
                        logging.warning(f"Vertex AI stream request encountered exception: {ex}. Retrying in {sleep_time:.2f}s (attempt {attempt}/{max_retries})...")
                        time.sleep(sleep_time)
                        token = get_adc_token(force=True)
                    else:
                        raise ex

            try:
                with resp:
                    self.send_response(resp.status)
                    for k, v in resp.headers.items():
                        if k.lower() not in ("content-length", "transfer-encoding"):
                            self.send_header(k, v)
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    
                    def write_chunk(data):
                        if not data:
                            return
                        self.wfile.write(f"{len(data):x}\r\n".encode('ascii'))
                        self.wfile.write(data)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()

                    # Translate Vertex AI SSE stream chunks to CCPA format
                    while True:
                        line = resp.readline()
                        if not line:
                            break
                        if line.startswith(b"data:"):
                            try:
                                sse_data = line[5:].strip()
                                if sse_data:
                                    # Log raw chunk
                                    with open("/tmp/mocker_stream.log", "a") as f_log:
                                        f_log.write(f"--- CHUNK ---\nRAW: {sse_data.decode('utf-8', errors='ignore')}\n")
                                    obj = json.loads(sse_data.decode("utf-8"))
                                    
                                    if is_anthropic:
                                        # Translate Anthropic stream event to Gemini candidate structure
                                        ev_type = obj.get("type", "")
                                        delta_text = ""
                                        if ev_type == "content_block_delta":
                                            delta = obj.get("delta", {})
                                            if delta.get("type") == "text_delta":
                                                delta_text = delta.get("text", "")
                                        elif ev_type == "message_start":
                                            delta_text = ""
                                            
                                        if delta_text:
                                            gemini_obj = {
                                                "candidates": [
                                                    {
                                                        "content": {
                                                            "role": "model",
                                                            "parts": [{"text": delta_text}]
                                                        }
                                                    }
                                                ]
                                            }
                                            wrapped = {"response": gemini_obj}
                                            wrapped_bytes = f"data: {json.dumps(wrapped)}\n".encode("utf-8")
                                            write_chunk(wrapped_bytes)
                                    else:
                                        # Wrap standard Gemini payload under a top-level "response" object
                                        wrapped = {"response": obj}
                                        wrapped_bytes = f"data: {json.dumps(wrapped)}\n".encode("utf-8")
                                        with open("/tmp/mocker_stream.log", "a") as f_log:
                                            f_log.write(f"WRAPPED: {json.dumps(wrapped)}\n")
                                        write_chunk(wrapped_bytes)
                            except Exception as parse_err:
                                logging.error(f"Failed to parse and wrap SSE chunk: {parse_err}. Original line: {line}")
                                with open("/tmp/mocker_stream.log", "a") as f_log:
                                    f_log.write(f"PARSE_ERR: {parse_err}. Line: {line!r}\n")
                                # Forward original line as fallback
                                write_chunk(line)
                        else:
                            with open("/tmp/mocker_stream.log", "a") as f_log:
                                f_log.write(f"NON-DATA LINE: {line!r}\n")
                            write_chunk(line)
                    # Write terminating chunk
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                return
            except Exception as e:
                logging.error(f"Vertex AI stream proxy failed: {e}")
                self.send_response(502)
                self.end_headers()
                self.wfile.write(f"Vertex AI Proxy Error: {e}".encode("utf-8"))
                return


        # Handle HasAuthToken Interception
        if "HasAuthToken" in self.path or "hasAuthToken" in self.path:
            body = json.dumps({"hasToken": True, "isGcpTos": True}).encode("utf-8")
            data_frame = b"\x00" + len(body).to_bytes(4, "big") + body
            trailer = b"grpc-status: 0\r\n"
            trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
            final_body = data_frame + trailer_frame
            self.send_response(200)
            self.send_header("Content-Type", "application/grpc-web+json")
            self.send_header("Content-Length", str(len(final_body)))
            self.end_headers()
            self.wfile.write(final_body)
            return

        # Handle GetAuthStatus Interception
        if "GetAuthStatus" in self.path or "getAuthStatus" in self.path:
            body = json.dumps({
                "authResult": {
                    "hasValidAuth": True,
                    "grantedScopes": ["https://www.googleapis.com/auth/cloud-platform"],
                    "isGcpTos": True
                }
            }).encode("utf-8")
            data_frame = b"\x00" + len(body).to_bytes(4, "big") + body
            trailer = b"grpc-status: 0\r\n"
            trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
            final_body = data_frame + trailer_frame
            self.send_response(200)
            self.send_header("Content-Type", "application/grpc-web+json")
            self.send_header("Content-Length", str(len(final_body)))
            self.end_headers()
            self.wfile.write(final_body)
            return

        # Handle LoginWithBrowser Interception
        if "LoginWithBrowser" in self.path or "loginWithBrowser" in self.path:
            body = json.dumps({
                "authResult": {
                    "hasValidAuth": True,
                    "grantedScopes": ["https://www.googleapis.com/auth/cloud-platform"],
                    "isGcpTos": True
                }
            }).encode("utf-8")
            data_frame = b"\x00" + len(body).to_bytes(4, "big") + body
            trailer = b"grpc-status: 0\r\n"
            trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
            final_body = data_frame + trailer_frame
            self.send_response(200)
            self.send_header("Content-Type", "application/grpc-web+json")
            self.send_header("Content-Length", str(len(final_body)))
            self.end_headers()
            self.wfile.write(final_body)
            return

        # Handle GetCascadeModelConfigs / GetCascadeModelConfigData / GetCommandModelConfigs Interception
        if "GetCascadeModelConfig" in self.path or "getCascadeModelConfig" in self.path or "GetCommandModelConfigs" in self.path or "getCommandModelConfigs" in self.path:
            cfg_data = build_cascade_model_config_data()
            body = json.dumps(cfg_data).encode("utf-8")
            data_frame = b"\x00" + len(body).to_bytes(4, "big") + body
            trailer = b"grpc-status: 0\r\n"
            trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
            final_body = data_frame + trailer_frame
            self.send_response(200)
            self.send_header("Content-Type", "application/grpc-web+json")
            self.send_header("Content-Length", str(len(final_body)))
            self.end_headers()
            self.wfile.write(final_body)
            return

        # 1. Handle GetUserStatus Interception
        if "GetUserStatus" in self.path or "getUserStatus" in self.path:
            status, resp_headers, resp_body = forward_request(self.path, "POST", self.headers, post_data)
            try:
                doc = None
                ctype_resp = resp_headers.get("Content-Type", "").lower()
                is_env = len(resp_body) >= 5 and resp_body[0] in (0x00, 0x80)
                if is_env:
                    plen = int.from_bytes(resp_body[1:5], "big")
                    payload = resp_body[5:5+plen]
                else:
                    payload = resp_body
                if payload:
                    try:
                        doc = json.loads(payload.decode("utf-8"))
                    except Exception:
                        pass
                
                if doc is None or not isinstance(doc, dict):
                    doc = {
                        "userStatus": {
                            "name": "admin_mgenchev_altostrat_com",
                            "userTier": {"availableCredits": [{"creditType": 1, "creditAmount": 1000}]},
                            "cascadeModelConfigData": build_cascade_model_config_data(),
                        }
                    }
                else:
                    us_obj = doc.setdefault("userStatus", {})
                    if isinstance(us_obj, dict):
                        us_obj["cascadeModelConfigData"] = build_cascade_model_config_data()
                        
                new_payload = json.dumps(doc).encode("utf-8")
                
                if "grpc" in ctype_resp or "grpc" in self.headers.get("Content-Type", ""):
                    data_frame = b"\x00" + len(new_payload).to_bytes(4, "big") + new_payload
                    trailer = b"grpc-status: 0\r\n"
                    trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
                    resp_body = data_frame + trailer_frame
                    resp_headers["Content-Type"] = "application/grpc-web+json"
                else:
                    resp_body = new_payload
                    resp_headers["Content-Type"] = "application/json"
                    
                status = 200
                logging.info("GetUserStatus response augmented successfully.")
            except Exception as e:
                logging.error(f"Failed to augment GetUserStatus response: {e}")
            
            self.send_response(status)
            for k, v in resp_headers.items():
                if k.lower() not in ("content-length", "transfer-encoding"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
            return

        # 2. Handle StartCascade Interception (Supports enveloped & non-enveloped JSON, and binary proto)
        if "StartCascade" in self.path or "startCascade" in self.path:
            body = post_data
            cascade_id = None
            try:
                if is_json:
                    is_env_json = len(body) >= 5 and body[0] in (0x00, 0x80)
                    if is_env_json:
                        plen = int.from_bytes(body[1:5], "big")
                        payload = body[5:5+plen]
                    else:
                        payload = body
                        
                    doc = json.loads(payload.decode("utf-8"))
                    cascade_id = doc.get("cascadeId") or doc.get("cascade_id") or doc.get("conversationId") or doc.get("conversation_id")
                    modified = inject_model_into_json_doc(doc, is_start_cascade=True)
                    
                    if modified:
                        new_payload = json.dumps(doc).encode("utf-8")
                        if is_env_json:
                            body = bytes([body[0]]) + len(new_payload).to_bytes(4, "big") + new_payload
                        else:
                            body = new_payload
                        logging.info("StartCascade JSON request modified. Injected DEFAULT_MODEL.")
                elif is_enveloped or is_raw_proto:
                    # Fallback to regex pattern matching on raw body for binary proto
                    try:
                        m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", body.decode("utf-8", errors="ignore"), re.IGNORECASE)
                        if m:
                            cascade_id = m.group(0)
                    except Exception as ex:
                        logging.error(f"Error regex matching cascade_id in binary StartCascade: {ex}")
            except Exception as e:
                logging.error(f"Failed to intercept/modify StartCascade request: {e}")

            if cascade_id:
                logging.info(f"StartCascade request for {cascade_id}. Clearing readiness event.")
                event = get_cascade_event(cascade_id)
                event.clear()

            # Synchronously forward the StartCascade request first
            status, resp_headers, resp_body = forward_request(self.path, "POST", self.headers, body)

            if status == 200:
                logging.info("StartCascade successfully forwarded. Aligning database trajectory IDs...")
                if not cascade_id:
                    # Extract cascade ID from request JSON or body
                    cascade_id = extract_cascade_id(body, is_json)
                
                if cascade_id:
                    logging.info(f"Extracted/Confirmed cascade_id: {cascade_id}. Performing database alignment...")
                    db_path = os.path.expanduser(f"~/.gemini/antigravity/conversations/{cascade_id}.db")
                    # Poll for file existence for up to 1.5 seconds (Go server usually writes it immediately)
                    db_found = False
                    for i in range(15):
                        if os.path.exists(db_path):
                            db_found = True
                            break
                        time.sleep(0.1)
                    
                    if db_found:
                        try:
                            import sqlite3
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()
                            
                            # Convert to WAL mode
                            cursor.execute("PRAGMA journal_mode;")
                            mode = cursor.fetchone()[0]
                            if mode.lower() != "wal":
                                logging.info(f"Converting {cascade_id}.db to WAL mode...")
                                cursor.execute("PRAGMA journal_mode=WAL;")
                                conn.commit()
                                
                            # Align trajectory_id
                            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trajectory_meta';")
                            if cursor.fetchone():
                                cursor.execute("UPDATE trajectory_meta SET trajectory_id = cascade_id WHERE trajectory_id != cascade_id;")
                                if conn.total_changes > 0:
                                    logging.info(f"Aligned trajectory_id with cascade_id inside {cascade_id}.db")
                                    conn.commit()
                            conn.close()
                        except Exception as e:
                            logging.error(f"Failed to align database {cascade_id}.db: {e}")
                    else:
                        logging.warning(f"Database file not found on disk for alignment: {db_path}")

                    # Mark this cascade as ready now!
                    event = get_cascade_event(cascade_id)
                    event.set()
                    logging.info(f"Marked cascade {cascade_id} as ready and set the event.")
                else:
                    logging.warning("Could not extract cascade_id from StartCascade request.")
            else:
                logging.warning(f"StartCascade forwarded but returned status {status}")
                if cascade_id:
                    # Set the event anyway to avoid infinite blocking of any waiters
                    event = get_cascade_event(cascade_id)
                    event.set()

            # Send response back to client
            self.send_response(status)
            for k, v in resp_headers.items():
                if k.lower() not in ("content-length", "transfer-encoding"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
            return

        # 3. Handle GetSlashCommands, SendUserCascadeMessage, StreamAgentStateUpdates, and other cascade requests
        cascade_endpoints = [
            "GetSlashCommands", "getSlashCommands",
            "SendUserCascadeMessage", "sendUserCascadeMessage",
            "StreamAgentStateUpdates", "streamAgentStateUpdates",
            "FetchConversationAnnotations", "fetchConversationAnnotations",
            "UpdateConversationAnnotations", "updateConversationAnnotations",
            "GetCascade", "getCascade"
        ]
        is_cascade_req = any(endpoint in self.path for endpoint in cascade_endpoints)
        if is_cascade_req:
            body = post_data
            
            # Extract cascade_id and wait on its event before forwarding
            cascade_id = extract_cascade_id(body, is_json)
            if cascade_id:
                logging.info(f"Intercepted {self.path} for cascade {cascade_id}. Waiting for DB readiness event...")
                event = get_cascade_event(cascade_id)
                if not event.wait(timeout=5.0):
                    logging.warning(f"Timed out waiting for cascade {cascade_id} readiness in {self.path}")
                else:
                    logging.info(f"Cascade {cascade_id} is ready. Forwarding {self.path}.")

            try:
                if is_json:
                    is_env_json = len(body) >= 5 and body[0] in (0x00, 0x80)
                    if is_env_json:
                        plen = int.from_bytes(body[1:5], "big")
                        payload = body[5:5+plen]
                    else:
                        payload = body
                        
                    doc = json.loads(payload.decode("utf-8"))
                    needs_model_injection = any(endpoint in self.path for endpoint in ("GetSlashCommands", "getSlashCommands", "SendUserCascadeMessage", "sendUserCascadeMessage"))
                    if needs_model_injection:
                        modified = inject_model_into_json_doc(doc, is_start_cascade=False)
                    else:
                        modified = False
                    
                    if modified:
                        new_payload = json.dumps(doc).encode("utf-8")
                        if is_env_json:
                            body = bytes([body[0]]) + len(new_payload).to_bytes(4, "big") + new_payload
                        else:
                            body = new_payload
                        logging.info(f"JSON request modified. Injected DEFAULT_MODEL into {self.path}.")
                elif is_enveloped or is_raw_proto:
                    pass
            except Exception as e:
                logging.error(f"Binary proto model injection failed for {self.path}: {e}")

            self.forward_and_stream(self.path, "POST", self.headers, body)
            return

        # Handle Knowledge Graph Long-Term Memory API
        if "/api/kg" in self.path:
            try:
                for candidate_dir in [
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_graph"),
                    os.path.expanduser("~/.gemini/antigravity/bin/knowledge_graph"),
                    "/tmp/antigravity-web-hub/src/knowledge_graph"
                ]:
                    if os.path.exists(candidate_dir) and candidate_dir not in sys.path:
                        sys.path.insert(0, candidate_dir)
                from kg_engine import get_kg_engine
                kg = get_kg_engine()
                
                if "subgraph" in self.path:
                    target_id = self.path.split("target=")[-1] if "target=" in self.path else "infra:n4_compute_vm"
                    ctx = kg.get_subgraph_context(target_id)
                    resp_obj = {"context": ctx, "target": target_id}
                elif "search" in self.path:
                    q = self.path.split("q=")[-1] if "q=" in self.path else ""
                    results = kg.search_nodes(q)
                    resp_obj = {"results": results, "query": q}
                elif "upsert" in self.path:
                    doc = json.loads(post_data.decode("utf-8")) if post_data else {}
                    node = kg.upsert_node(doc.get("id", "entity"), doc.get("label", "Entity"), doc.get("type", "entity"), doc.get("description", ""))
                    resp_obj = {"status": "success", "node": node}
                else:
                    resp_obj = {"nodes": list(kg.nodes.values()), "edges": kg.edges, "version": "1.0"}
                
                body = json.dumps(resp_obj).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as ex:
                logging.error(f"KG API Error in do_POST: {ex}")
                err_body = json.dumps({"error": str(ex)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_body)))
                self.end_headers()
                self.wfile.write(err_body)
                return

        # 4. Handle CCPA Mocking
        response_data = {}
        if "loadCodeAssist" in self.path:
            response_data = {
                "response": {
                    "userTier": {
                        "availableCredits": [{
                            "creditType": 1,
                            "creditAmount": 1000,
                            "minimumCreditAmountForUsage": 0,
                        }]
                    },
                    "cloudaicompanionProject": PROJECT_ID,
                }
            }
        elif "fetchUserInfo" in self.path:
            response_data = {
                "userSettings": {"telemetryEnabled": False},
                "email": self.headers.get('X-User-Email') or self.headers.get('X-Goog-Authenticated-User-Email') or os.environ.get('CCPA_MOCK_EMAIL', 'admin@example.com'),
                "userTier": {"userTier": "USER_TIER_PRO"},
            }
        elif "listExperiments" in self.path or "ListExperiments" in self.path:
            response_data = {
                "experiments": []
            }
        elif "fetchAdminControls" in self.path:
            response_data = {
                "adminControls": {
                    "enableCodeAssist": True,
                    "enableEnterpriseSearch": True,
                }
            }
        elif "fetchAvailableModels" in self.path:
            response_data = {
                "models": {
                    "gemini-3.7-flash": {
                        "displayName": "Gemini 3.7 Flash",
                        "supportsImages": True,
                        "supportsThinking": True,
                        "recommended": True,
                        "maxTokens": 1048576,
                        "maxOutputTokens": 65536,
                        "model": 352,
                        "apiProvider": 2
                    },
                    "gemini-2.5-flash": {
                        "displayName": "Gemini 2.5 Flash",
                        "supportsImages": True,
                        "supportsThinking": True,
                        "maxTokens": 1048576,
                        "maxOutputTokens": 65536,
                        "model": 312,
                        "apiProvider": 2
                    },
                    "gemini-3.6-flash": {
                        "displayName": "Gemini 3.6 Flash",
                        "supportsImages": True,
                        "supportsThinking": True,
                        "maxTokens": 1048576,
                        "maxOutputTokens": 65536,
                        "model": 350,
                        "apiProvider": 2
                    },
                    "gemini-3.5-flash-lite": {
                        "displayName": "Gemini 3.5 Flash Lite",
                        "supportsImages": True,
                        "maxTokens": 1048576,
                        "maxOutputTokens": 65536,
                        "model": 330,
                        "apiProvider": 2
                    },
                    "claude-3-7-sonnet": {
                        "displayName": "Claude 3.7 Sonnet (Vertex AI)",
                        "supportsImages": True,
                        "supportsThinking": True,
                        "maxTokens": 200000,
                        "maxOutputTokens": 8192,
                        "model": 333,
                        "apiProvider": 2
                    },
                    "claude-opus-5": {
                        "displayName": "Claude Opus 5 (Vertex AI)",
                        "supportsImages": True,
                        "supportsThinking": True,
                        "maxTokens": 200000,
                        "maxOutputTokens": 8192,
                        "model": 290,
                        "apiProvider": 2
                    },
                    "claude-fable-5": {
                        "displayName": "Claude Fable 5 (Next-Gen)",
                        "supportsImages": True,
                        "supportsThinking": True,
                        "maxTokens": 200000,
                        "maxOutputTokens": 8192,
                        "model": 340,
                        "apiProvider": 2
                    }
                },
                "defaultAgentModelId": "gemini-3.7-flash",
                "agentModelSorts": [
                    {
                        "name": "Recommended",
                        "groups": [
                            {
                                "groupName": "",
                                "modelIds": [
                                    "gemini-3.7-flash",
                                    "gemini-3.6-flash",
                                    "gemini-3.5-flash-lite",
                                    "claude-3-7-sonnet",
                                    "claude-opus-5",
                                    "claude-fable-5"
                                ]
                            }
                        ]
                    }
                ]
            }

            
        response_bytes = json.dumps(response_data).encode('utf-8')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)
        logging.info(f"--- SENT RESPONSE ---")

    def do_GET(self):
        logging.info(f"--- RECEIVED GET ---")
        logging.info(f"Path: {self.path}")
        
        if "/api/kg" in self.path:
            try:
                for candidate_dir in [
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_graph"),
                    os.path.expanduser("~/.gemini/antigravity/bin/knowledge_graph"),
                    "/tmp/antigravity-web-hub/src/knowledge_graph"
                ]:
                    if os.path.exists(candidate_dir) and candidate_dir not in sys.path:
                        sys.path.insert(0, candidate_dir)
                from kg_engine import get_kg_engine
                kg = get_kg_engine()
                
                if "subgraph" in self.path:
                    target_id = self.path.split("target=")[-1] if "target=" in self.path else "infra:n4_compute_vm"
                    ctx = kg.get_subgraph_context(target_id)
                    resp_obj = {"context": ctx, "target": target_id}
                elif "search" in self.path:
                    q = self.path.split("q=")[-1] if "q=" in self.path else ""
                    results = kg.search_nodes(q)
                    resp_obj = {"results": results, "query": q}
                else:
                    resp_obj = {"nodes": list(kg.nodes.values()), "edges": kg.edges, "version": "1.0"}
                
                body = json.dumps(resp_obj).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as ex:
                logging.error(f"KG API Error in do_GET: {ex}")
                err_body = json.dumps({"error": str(ex)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_body)))
                self.end_headers()
                self.wfile.write(err_body)
                return

        if "/api/create-project-dir" in self.path:
            import urllib.parse
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            name = params.get("name", [""])[0]
            if name and re.match(r"^[a-zA-Z0-9_-]+$", name):
                dir_path = f"/mnt/data/projects/{name}"
                logging.info(f"Creating project directory: {dir_path}")
                os.makedirs(dir_path, exist_ok=True)
                os.chmod(dir_path, 0o777)
                try:
                    import shutil
                    import getpass
                    username = os.environ.get("USER") or getpass.getuser()
                    shutil.chown(dir_path, username, username)
                except Exception as ex:
                    logging.error(f"Failed to chown: {ex}")
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "path": dir_path}).encode("utf-8"))
                return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b"{}")

socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), CCPAHandler) as httpd:
    logging.info(f"Starting CCPA Mock Server on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

