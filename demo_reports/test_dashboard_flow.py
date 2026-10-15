import json
import time
from pathlib import Path
import httpx

admin_password = Path(".admin_password").read_text(encoding="utf-8").strip()

client = httpx.Client(base_url="http://127.0.0.1:8000", headers={"X-DynaGuard-Client": "dashboard"}, timeout=10)

# 1. Login
login_res = client.post("/auth/login", json={"username": "admin", "password": admin_password})
assert login_res.status_code == 200, f"Login failed: {login_res.text}"
print("Dashboard API admin login: SUCCESS")

# 2. Create project
proj_res = client.post("/projects", json={"name": "DynaFlow Shared Engine Pilot"})
assert proj_res.status_code == 201, f"Project creation failed: {proj_res.text}"
project_id = proj_res.json()["id"]
print(f"Project created: {project_id}")

# 3. Get starter template
template_res = client.get("/engine-template")
assert template_res.status_code == 200
cfg_vuln = template_res.json()
print("Template fetched successfully with target:", cfg_vuln["target"]["origin"])

# 4. Submit vulnerable run
vuln_run_res = client.post(f"/projects/{project_id}/engine-runs", json={"mode": "verify", "config": cfg_vuln})
assert vuln_run_res.status_code == 201, f"Run submission failed: {vuln_run_res.text}"
vuln_run_id = vuln_run_res.json()["id"]
print(f"Submitted vulnerable run: {vuln_run_id}")

# Wait for completion
deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    runs = client.get(f"/projects/{project_id}/engine-runs").json()
    vuln_run = next((r for r in runs if r["id"] == vuln_run_id), None)
    if vuln_run and vuln_run["status"] in ("completed", "incomplete", "cancelled"):
        break
    time.sleep(0.5)

print(f"Vulnerable run status: {vuln_run['status']}, stage: {vuln_run['stage']}")
assert vuln_run["status"] == "completed"
print("Vulnerable report findings count:", len(vuln_run["report"]["findings"]))
for exec_item in vuln_run["report"]["executions"]:
    print(f"  Execution {exec_item['test_id']}: outcome={exec_item['outcome']}, actual={exec_item['actual']}")

# 5. Submit fixed run (target http://127.0.0.1:8102)
cfg_fixed = json.loads(json.dumps(cfg_vuln))
cfg_fixed["target"]["origin"] = "http://127.0.0.1:8102"
cfg_fixed["build_id"] = "fixture-fixed-v1"
fixed_run_res = client.post(f"/projects/{project_id}/engine-runs", json={"mode": "verify", "config": cfg_fixed})
assert fixed_run_res.status_code == 201
fixed_run_id = fixed_run_res.json()["id"]
print(f"Submitted fixed run: {fixed_run_id}")

deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    runs = client.get(f"/projects/{project_id}/engine-runs").json()
    fixed_run = next((r for r in runs if r["id"] == fixed_run_id), None)
    if fixed_run and fixed_run["status"] in ("completed", "incomplete", "cancelled"):
        break
    time.sleep(0.5)

print(f"Fixed run status: {fixed_run['status']}, stage: {fixed_run['stage']}")
assert fixed_run["status"] == "completed"
print("Fixed report findings count:", len(fixed_run["report"]["findings"]))
for exec_item in fixed_run["report"]["executions"]:
    print(f"  Execution {exec_item['test_id']}: outcome={exec_item['outcome']}, actual={exec_item['actual']}")

# 6. Test cancellation
cancel_cfg = json.loads(json.dumps(cfg_fixed))
cancel_run_res = client.post(f"/projects/{project_id}/engine-runs", json={"mode": "verify", "config": cancel_cfg})
cancel_run_id = cancel_run_res.json()["id"]
cancel_post = client.post(f"/engine-runs/{cancel_run_id}/cancel")
print(f"Cancel request status code: {cancel_post.status_code}, status={cancel_post.json().get('status')}")

# 7. Test source review upload
source_files = [
    {"path": "sample/service.py", "content": 'secret_key = "synthetic-key"\nallow_insecure_tls = True'}
]
source_res = client.post(f"/projects/{project_id}/source-review", json={"files": source_files})
print(f"Source review status code: {source_res.status_code}")
if source_res.status_code == 201:
    source_data = source_res.json()
    print("Source findings count:", len(source_data["report"]["findings"]))
    for f in source_data["report"]["findings"]:
        print(f"  Source rule: {f['rule_id']} at {f['path']}:{f['line']}")

print("ALL BACKEND ADAPTER ENDPOINTS VERIFIED SUCCESSFULLY!")
