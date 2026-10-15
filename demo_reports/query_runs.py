from pathlib import Path
import httpx

admin_password = Path(".admin_password").read_text(encoding="utf-8").strip()
client = httpx.Client(base_url="http://127.0.0.1:8000", headers={"X-DynaGuard-Client": "dashboard"})
client.post("/auth/login", json={"username": "admin", "password": admin_password})

for p in client.get("/projects").json():
    print(f"Project: {p['name']} ({p['id']})")
    runs = client.get(f"/projects/{p['id']}/engine-runs").json()
    for r in runs:
        findings = len(r["report"]["findings"]) if r.get("report") else 0
        execs = [f"{e['test_id']}: {e['outcome']}" for e in r["report"]["executions"]] if r.get("report") else []
        print(f"  Run {r['id'][:8]} | mode={r['mode']} | status={r['status']} | findings={findings} | execs={execs}")
