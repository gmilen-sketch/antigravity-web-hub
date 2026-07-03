import http.server
import socketserver
import json
import logging
import os
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

PORT = 8083

DEFAULT_MODEL_ENUM = 312
DEFAULT_MODEL_NAME = "MODEL_GOOGLE_GEMINI_2_5_FLASH"

DROPDOWN_MODELS = [
    ("Gemini 3.5 Flash",              312),
    ("Gemini 3.1 Flash Lite Preview", 314),
    ("Gemini 3.1 Pro",                313),
    ("Claude Opus 4.8",               290),
    ("Claude Fable 5",                340),
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

class CCPAHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logging.info("%s - - %s" % (self.address_string(), format%args))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        logging.info(f"--- RECEIVED POST ---")
        logging.info(f"Path: {self.path}")
        
        # 1. Handle GetUserStatus Interception
        if "GetUserStatus" in self.path or "getUserStatus" in self.path:
            status, resp_headers, resp_body = forward_request(self.path, "POST", self.headers, post_data)
            if status == 200:
                try:
                    ctype = resp_headers.get("Content-Type", "").lower()
                    if "json" in ctype:
                        is_enveloped = len(resp_body) >= 5 and resp_body[0] in (0x00, 0x80)
                        if is_enveloped:
                            plen = int.from_bytes(resp_body[1:5], "big")
                            payload = resp_body[5:5+plen]
                        else:
                            payload = resp_body
                            
                        doc = json.loads(payload.decode("utf-8"))
                        us_obj = doc.setdefault("userStatus", {})
                        if isinstance(us_obj, dict):
                            us_obj["cascadeModelConfigData"] = build_cascade_model_config_data()
                            
                        new_payload = json.dumps(doc).encode("utf-8")
                        
                        if is_enveloped:
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

        # 2. Handle StartCascade Interception
        if "StartCascade" in self.path or "startCascade" in self.path:
            body = post_data
            try:
                is_enveloped = len(body) >= 5 and body[0] in (0x00, 0x80)
                if is_enveloped:
                    plen = int.from_bytes(body[1:5], "big")
                    if 5 + plen == len(body):
                        payload = body[5:]
                        doc = json.loads(payload.decode("utf-8"))
                        modified = False
                        
                        if _is_unset_enum(doc.get("requestedModel")) and _is_unset_enum(doc.get("requested_model")):
                            doc["requestedModel"] = moa(DEFAULT_MODEL_ENUM)
                            modified = True
                            
                        cascade_cfg = doc.setdefault("cascadeConfig", {})
                        if isinstance(cascade_cfg, dict):
                            planner_cfg = cascade_cfg.setdefault("plannerConfig", {})
                            if isinstance(planner_cfg, dict):
                                if _is_unset_enum(planner_cfg.get("planModel")):
                                    planner_cfg["planModel"] = DEFAULT_MODEL_NAME
                                    modified = True
                                if _is_unset_enum(planner_cfg.get("requestedModel")):
                                    planner_cfg["requestedModel"] = moa(DEFAULT_MODEL_ENUM)
                                    modified = True
                                    
                                conv = planner_cfg.get("conversational")
                                if isinstance(conv, dict) and conv.get("agenticMode"):
                                    conv["agenticMode"] = False
                                    modified = True
                                    
                            executor_cfg = cascade_cfg.setdefault("executorConfig", {})
                            if isinstance(executor_cfg, dict) and not executor_cfg.get("disableEmptyOutputContinuation"):
                                executor_cfg["disableEmptyOutputContinuation"] = True
                                modified = True
                                
                        if modified:
                            new_payload = json.dumps(doc).encode("utf-8")
                            body = bytes([body[0]]) + len(new_payload).to_bytes(4, "big") + new_payload
                            logging.info("StartCascade request modified. Injected DEFAULT_MODEL.")
            except Exception as e:
                logging.error(f"Failed to intercept/modify StartCascade request: {e}")

            status, resp_headers, resp_body = forward_request(self.path, "POST", self.headers, body)
            self.send_response(status)
            for k, v in resp_headers.items():
                if k.lower() not in ("content-length", "transfer-encoding"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(resp_body)))
            self.end_headers()
            self.wfile.write(resp_body)
            return

        # 3. Handle CCPA Mocking
        response_data = {}
        if "loadCodeAssist" in self.path:
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
                ],
                "userInfo": {
                    "email": self.headers.get('X-User-Email') or self.headers.get('X-Goog-Authenticated-User-Email') or os.environ.get('CCPA_MOCK_EMAIL', 'admin@mgenchev.altostrat.com'),
                    "signedIn": True
                }
            }
        elif "listExperiments" in self.path or "ListExperiments" in self.path:
            response_data = {
                "experiments": []
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
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b"{}")

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), CCPAHandler) as httpd:
    logging.info(f"Starting CCPA Mock Server on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
