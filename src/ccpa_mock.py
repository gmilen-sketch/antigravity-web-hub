import http.server
import socketserver
import json
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

PORT = 8083

class CCPAHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Override to use logging module instead of stderr
        logging.info("%s - - %s" % (self.address_string(), format%args))

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        logging.info(f"--- RECEIVED POST ---")
        logging.info(f"Path: {self.path}")
        logging.info(f"Headers: {dict(self.headers)}")
        try:
            # Try to decode and print as JSON
            data = json.loads(post_data.decode('utf-8'))
            logging.info(f"Body (JSON): {json.dumps(data, indent=2)}")
        except Exception:
            logging.info(f"Body (Raw): {post_data}")
        
        # Determine the response based on the path
        response_data = {}
        
        # Let's provide a basic structure if needed
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
        logging.info(f"Body: {response_data}\n")

    def do_GET(self):
        logging.info(f"--- RECEIVED GET ---")
        logging.info(f"Path: {self.path}")
        logging.info(f"Headers: {dict(self.headers)}")
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b"{}")

with socketserver.TCPServer(("127.0.0.1", PORT), CCPAHandler) as httpd:
    logging.info(f"Starting CCPA Mock Server on port {PORT}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
