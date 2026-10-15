import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import httpx
from dynaguard.config import ProjectConfig
from dynaguard.discovery import discover

SECRET = "synthetic-demo-password"
os.environ["DYNAGUARD_TEST_PASSWORD"] = SECRET

class DemoApp(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path == "/app":
            body = b'<!doctype html><html><head><title>App</title></head><body><h1>Dashboard</h1><div id="user">Loading...</div><a href="/app/help">Help</a><script src="/asset.js"></script></body></html>'
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(body)
        elif self.path == "/asset.js":
            body = b'fetch("/api/me").then(r=>r.json()).then(d=>{document.getElementById("user").textContent=d.name;});'
            self.send_response(200); self.send_header("Content-Type", "application/javascript"); self.end_headers(); self.wfile.write(body)
        elif self.path == "/api/me":
            auth = self.headers.get("authorization", "")
            if auth == "Bearer member-secret-token":
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"name": "demo-member"}')
            else:
                self.send_response(401); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/session":
            content_len = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(content_len))
            if data.get("passcode") == SECRET:
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b'{"session": {"token": "member-secret-token"}}')
            else:
                self.send_response(401); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

server = ThreadingHTTPServer(("127.0.0.1", 0), DemoApp)
port = server.server_port
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
origin = f"http://127.0.0.1:{port}"

config = ProjectConfig.model_validate({
    "project": "Live Browser Discovery Demo",
    "build_id": "discovery-v1",
    "target": {
        "origin": origin,
        "pinned_ips": ["127.0.0.1"],
        "allow_private": True,
        "allowed_paths": ["/session", "/api/me", "/app", "/asset.js"]
    },
    "identities": {
        "member": {
            "kind": "json_login",
            "login_path": "/session",
            "username": "member",
            "username_field": "email",
            "password_field": "passcode",
            "password_env": "DYNAGUARD_TEST_PASSWORD",
            "token_field": "session.token",
            "auth_check": {"path": "/api/me", "expected": {"name": "demo-member"}}
        }
    },
    "tests": [],
    "discovery_paths": ["/app"],
    "discovery_identity": "member"
})

Path("demo_reports/discovery-config.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")
report = asyncio.run(discover(config))
Path("demo_reports/discovery-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

print(f"Status: {report['status']}")
print(f"Coverage: {json.dumps(report['coverage'])}")
print(f"Pages: {json.dumps(report['pages'])}")
print("Requests:")
for req in report["requests"]:
    print(f"  {req.get('method')} {req.get('path')} -> {req.get('status', 'blocked: ' + str(req.get('blocked')))}")

server.shutdown(); server.server_close()
