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

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
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

def get_adc_token() -> str:
    """Fetches and caches fresh GCP OAuth access token via ADC."""
    now = time.time()
    if now < _token_cache["expires_at"]:
        return _token_cache["token"]
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "application-default", "print-access-token"],
            text=True,
        ).strip()
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + 3000
        logging.info("Fetched fresh ADC token for Vertex AI bridge.")
        return token
    except Exception as e:
        logging.error(f"Failed to fetch ADC token: {e}")
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
    if not requested_model_from_payload or not isinstance(requested_model_from_payload, str):
        return "gemini-3.5-flash"
    req_lower = requested_model_from_payload.lower()
    if "pro" in req_lower:
        return "gemini-3.1-pro-preview"
    if "lite" in req_lower:
        return "gemini-3.1-flash-lite"
    return "gemini-3.5-flash"

PORT = 8083

DEFAULT_MODEL_ENUM = 348
DEFAULT_MODEL_NAME = "MODEL_GOOGLE_GEMINI_RIFTRUNNER"

DROPDOWN_MODELS = [
    ("Gemini 3.5 Flash",              348),
    ("Gemini 3.1 Flash Lite Preview", 330),
    ("Gemini 3.1 Pro",                343),
]


def moa(val):
    return {"choice": {"case": "model", "value": val}}

def build_cascade_model_config_data():
    return {
        "clientModelConfigs": [
            {
                "label": label,
                "modelOrAlias": moa(val),
                "disabled": False,
                "supportedMimeTypes": {},
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

def inject_model_into_json_doc(doc, is_start_cascade=False):
    modified = False

    # 1. Normalize top-level requestedModel (StartCascadeRequest specific)
    req_model = doc.get("requestedModel") or doc.get("requested_model")
    if "requested_model" in doc:
        del doc["requested_model"]
        modified = True

    if is_start_cascade:
        if req_model is not None:
            if isinstance(req_model, dict):
                val = None
                choice = req_model.get("choice", {})
                if isinstance(choice, dict):
                    val = choice.get("value")
                if val is None:
                    val = req_model.get("model") or req_model.get("value")
                
                if val is not None and val != 0 and val != "" and val != "MODEL_UNSPECIFIED":
                    target_val = val
                else:
                    target_val = DEFAULT_MODEL_NAME
            elif _is_unset_enum(req_model):
                target_val = DEFAULT_MODEL_NAME
            else:
                target_val = req_model
            
            doc["requestedModel"] = target_val
            modified = True
        else:
            doc["requestedModel"] = DEFAULT_MODEL_NAME
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
            pm_val = planner_cfg.get("planModel") or planner_cfg.get("plan_model")
            if "plan_model" in planner_cfg:
                del planner_cfg["plan_model"]
                modified = True

            if _is_unset_enum(pm_val):
                planner_cfg["planModel"] = DEFAULT_MODEL_NAME
                modified = True
            else:
                planner_cfg["planModel"] = pm_val

            # 5. Normalize requestedModel / requested_model (this is ModelOrAlias, i.e., dictionary)
            rm_val = planner_cfg.get("requestedModel") or planner_cfg.get("requested_model")
            if "requested_model" in planner_cfg:
                del planner_cfg["requested_model"]
                modified = True

            if _is_unset_enum(rm_val):
                planner_cfg["requestedModel"] = {"model": DEFAULT_MODEL_NAME}
                modified = True
            else:
                if isinstance(rm_val, dict):
                    planner_cfg["requestedModel"] = rm_val
                else:
                    planner_cfg["requestedModel"] = {"model": rm_val}
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
        
        logging.info(f"Request Content-Type Raw: {ctype_raw!r}, Parsed: {ctype!r}, is_enveloped: {is_enveloped}, is_raw_proto: {is_raw_proto}, is_json: {is_json}")
        
        if "streamGenerateContent" in self.path:
            logging.info(f"--- STREAM GENERATE CONTENT INTERCEPTED ---")
            
            token = get_adc_token()
            if not token:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"No ADC Token Available")
                return

            model = "gemini-3.5-flash"
            payload_bytes = post_data
            try:
                doc = json.loads(post_data.decode("utf-8"))
                logging.info(f"Payload: {json.dumps(doc, indent=2)}")
                with open("/tmp/stream_req.json", "w") as f:
                    json.dump(doc, f, indent=2)
                
                # Dynamically extract and map the requested model if possible
                req_model = doc.get("model") or doc.get("modelName") or doc.get("model_name")
                if req_model:
                    model = map_model_name(req_model)
                
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
                    
                    # Prevent thinkingConfig compatibility issues for non-reasoning models
                    if "generationConfig" in cleaned_req:
                        gen_cfg = cleaned_req["generationConfig"]
                        if isinstance(gen_cfg, dict) and "thinkingConfig" in gen_cfg:
                            del gen_cfg["thinkingConfig"]
                    
                    payload_bytes = json.dumps(cleaned_req).encode("utf-8")
                    logging.info(f"Forwarding cleaned standard payload for Vertex AI.")
            except Exception as e:
                logging.error(f"Failed to parse and clean streamGenerateContent payload: {e}")

            # Use v1beta1 REST endpoint with 'global' location as verified working
            vertex_url = f"https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/global/publishers/google/models/{model}:streamGenerateContent?alt=sse"
            logging.info(f"Forwarding streamGenerateContent to Vertex AI: {vertex_url}")
            
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
                    if he.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                        sleep_time = backoff_base * (2 ** (attempt - 1))
                        logging.warning(f"Vertex AI stream request returned HTTP {he.code}. Retrying in {sleep_time:.2f}s (attempt {attempt}/{max_retries})...")
                        time.sleep(sleep_time)
                        token = get_adc_token()
                    else:
                        raise he
                except Exception as ex:
                    if attempt < max_retries:
                        sleep_time = backoff_base * (2 ** (attempt - 1))
                        logging.warning(f"Vertex AI stream request encountered exception: {ex}. Retrying in {sleep_time:.2f}s (attempt {attempt}/{max_retries})...")
                        time.sleep(sleep_time)
                        token = get_adc_token()
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

        # 1. Handle GetUserStatus Interception
        if "GetUserStatus" in self.path or "getUserStatus" in self.path:
            status, resp_headers, resp_body = forward_request(self.path, "POST", self.headers, post_data)
            if status == 200:
                try:
                    ctype_resp = resp_headers.get("Content-Type", "").lower()
                    if "json" in ctype_resp:
                        is_env = len(resp_body) >= 5 and resp_body[0] in (0x00, 0x80)
                        if is_env:
                            plen = int.from_bytes(resp_body[1:5], "big")
                            payload = resp_body[5:5+plen]
                        else:
                            payload = resp_body
                            
                        doc = json.loads(payload.decode("utf-8"))
                        us_obj = doc.setdefault("userStatus", {})
                        if isinstance(us_obj, dict):
                            us_obj["cascadeModelConfigData"] = build_cascade_model_config_data()
                            
                        new_payload = json.dumps(doc).encode("utf-8")
                        
                        if is_env:
                            data_frame = b"\x00" + len(new_payload).to_bytes(4, "big") + new_payload
                            trailer = b"grpc-status: 0\r\n"
                            trailer_frame = b"\x80" + len(trailer).to_bytes(4, "big") + trailer
                            final_body = data_frame + trailer_frame
                        else:
                            final_body = new_payload
                            
                        logging.info("GetUserStatus response augmented successfully.")
                        resp_body = final_body
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
                    # StartCascadeRequest.requested_model (field 14, enum) = 348 -> varint(348)=\xdc\x02
                    extra = b"\x70\xdc\x02"
                    if is_raw_proto:
                        body = body + extra
                        logging.info("Injected raw-proto model bytes for StartCascade")
                    elif is_enveloped and len(body) >= 5 and body[0] in (0x00, 0x80):
                        payload_len = int.from_bytes(body[1:5], "big")
                        new_payload = body[5:5+payload_len] + extra
                        new_header = bytes([body[0]]) + len(new_payload).to_bytes(4, "big")
                        body = new_header + new_payload
                        logging.info("Injected enveloped model bytes for StartCascade")
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
                    cascade_cfg_field = None
                    if "GetSlashCommands" in self.path or "getSlashCommands" in self.path:
                        cascade_cfg_field = 1  # GetSlashCommandsRequest.cascade_config
                    elif "SendUserCascadeMessage" in self.path or "sendUserCascadeMessage" in self.path:
                        cascade_cfg_field = 5  # SendUserCascadeMessageRequest.cascade_config
                        
                    extra = b""
                    if cascade_cfg_field is not None:
                        # CascadePlannerConfig.plan_model = 348 (RIFTRUNNER) -> \x08\xdc\x02
                        # CascadeConfig.planner_config (field 1, message) -> \x0a\x03\x08\xdc\x02
                        inner = b"\x0a\x03\x08\xdc\x02"
                        cc_tag = (cascade_cfg_field << 3) | 2
                        extra = bytes([cc_tag, len(inner)]) + inner
                        
                    if extra:
                        if is_raw_proto:
                            body = body + extra
                            logging.info(f"Injected raw-proto model bytes (+{len(extra)}B) for {self.path}")
                        elif is_enveloped and len(body) >= 5 and body[0] in (0x00, 0x80):
                            payload_len = int.from_bytes(body[1:5], "big")
                            new_payload = body[5:5+payload_len] + extra
                            new_header = bytes([body[0]]) + len(new_payload).to_bytes(4, "big")
                            body = new_header + new_payload
                            logging.info(f"Injected enveloped model bytes (+{len(extra)}B) for {self.path}")
            except Exception as e:
                logging.error(f"Binary proto model injection failed for {self.path}: {e}")

            self.forward_and_stream(self.path, "POST", self.headers, body)
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
                "email": self.headers.get('X-User-Email') or self.headers.get('X-Goog-Authenticated-User-Email') or os.environ.get('CCPA_MOCK_EMAIL', 'user@example.com'),
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
                "availableModels": [
                    {
                        "name": "gemini-3.5-flash",
                        "displayName": "Gemini 3.5 Flash",
                        "supportedFeatures": ["CHAT"]
                    },
                    {
                        "name": "gemini-3.1-pro-preview",
                        "displayName": "Gemini 3.1 Pro",
                        "supportedFeatures": ["CHAT"]
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

