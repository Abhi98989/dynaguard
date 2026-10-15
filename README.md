# DynaGuard

DynaGuard is an internal security-validation tool with a **local terminal CLI and a web dashboard using the same Python engine**. It reviews selected source patterns, performs configured read-permission tests against running applications, and records what each test actually proved.

This release replaces the fixture-only restriction for new shared-engine runs. The original Alice/Bob demo and its historical results remain available separately.

**A completed run is not a declaration that an application is secure.** The reports distinguish suspected source issues, confirmed permission bypasses, passed assertions, and incomplete checks.

## What works in this release

| Capability | CLI | Dashboard | Boundaries |
|---|---|---|---|
| Source review | Repository directory | Selected text-file upload | Seven heuristic patterns; no dataflow or dependency advisory engine |
| HTTP/HTTPS permission tests | JSON configuration | Same JSON configuration | Read access to designated synthetic resources |
| Authentication | Anonymous, bearer token, JSON login | Same | JSON login supports bearer response or session cookies; no OAuth/MFA/form automation |
| Multiple tests per run | Yes | Yes | Shared-engine reports retain separate executions and findings |
| Browser discovery | Optional Playwright extra | Optional browser worker | Renders explicitly listed pages, lists links and captures permitted requests |
| Frontend exposure review | Through browser discovery | Through browser discovery | Heuristic inspection of delivered text/JS/JSON; secret values omitted |
| Evidence/reporting | JSON and escaped HTML | JSON report/download and evidence viewer | Root causes are not invented from a status code |
| Retest | Repeat one unchanged test contract | Edit build label and start a new shared-engine run | Automatic linked retest is CLI-only for new engine runs; legacy UI retests remain |
| Cancellation | Ctrl+C | Cancel queued/running jobs | Incomplete/cancelled runs do not count as passes |

Not implemented: general injection exploitation, write-workflow manipulation, attack-chain planning, database connections/policy adapters, mobile analysis, repository Git-history scanning, Semgrep/Trivy/ZAP integrations, automatic code repair or AI root-cause analysis. Database-related source patterns are heuristics, not a database security audit.

## Quick start: local CLI

Python **3.12+** is required. Run from the repository root:

```bash
python -m venv .venv
```

Activate the environment:

```bash
# macOS/Linux
source .venv/bin/activate
```

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Install the CLI and scan a local repository:

```bash
python -m pip install -e ./backend
dynaguard scan source --path /path/to/your/project --output source-report.json
dynaguard report --input source-report.json --output source-report.html
```

Use a quoted Windows path such as `--path "C:\Projects\DynaFlow"` where applicable. No dashboard account, database or source upload is required for CLI scans. The CLI does not install or execute the scanned project's dependencies.

### Configure a running application

```bash
dynaguard init --output dynaguard.json
```

This creates a **local fixture example**, not a ready-made configuration for DynaFlow. Edit it for your actual environment. Never put passwords or private tokens directly in JSON. Use environment-variable references such as `DYNAGUARD_TEST_MEMBER_PASSWORD`.

```bash
dynaguard verify --config dynaguard.json --output verification.json
dynaguard report --input verification.json --output verification.html
```

Before running, define the referenced test credentials in your shell or secret-management environment. The target must be running; DynaGuard does not launch an arbitrary repository's application automatically.

CLI exit codes:

- `0`: all selected work completed with no findings. Only the stated coverage applies.
- `1`: work completed with findings, including suspected heuristic findings.
- `2`: configuration/operational error or incomplete work. Findings may still exist in a partial report.
- `130`: interrupted by the operator.

### Reproduce the included local permission test

Install the backend dependencies, then start the synthetic fixture in one terminal:

```bash
python -m pip install -r backend/requirements.txt
# Set FIXTURE_PASSWORD to a disposable test-only password in this terminal.
# Set FIXTURE_MODE=vulnerable for the initial demonstration.
cd backend
python -m uvicorn fixture.main:app --host 127.0.0.1 --port 8101 --no-access-log
```

In another activated terminal, with the same `FIXTURE_PASSWORD` environment value:

```bash
dynaguard verify --config examples/fixture.json --output vulnerable.json
```

Stop the fixture, set `FIXTURE_MODE=fixed`, and restart it at the same address. Then:

```bash
dynaguard retest --config examples/fixture.json --report vulnerable.json --test-id records.cross-owner --output retest.json
```

The retest checks the same project, target and test-contract hash. A changed test must run as a new scan. The original report is never overwritten by retesting unless you explicitly choose the same output filename; use distinct output files.

The fixture is deliberately vulnerable in one mode. Keep it bound to loopback or the isolated Compose network.

## Web dashboard

The existing local dashboard remains available:

```bash
python scripts/setup.py
docker compose up --build -d
```

Open **http://127.0.0.1:3000** and use the administrator password chosen during setup. Database migrations run before the API and worker start.

1. Create/select a project.
2. Open **Shared engine · configurable application tests**.
3. Edit the JSON configuration: origin, pinned addresses, allowed paths, identities and resource assertions.
4. Select **Verify permissions** or **Discover live pages**.
5. Expand the run to see coverage, individual outcomes, findings, evidence and limitations.
6. Download the report or cancel unfinished work.

The selected-source upload accepts at most 100 files and a server request body of 2 MiB. File contents go to your DynaGuard server, are scanned in a temporary directory and then deleted. Reports omit source snippets and secret values. Use the CLI for large repositories or when code must stay on your machine.

### Register a real staging target

The default Compose setup still has isolated fixture-only networks. **A public URL will not become reachable just because it is pasted into the UI.** This prevents the dashboard from turning into an unrestricted network requester.

For a real staging application:

- Put the exact origin and its expected IP addresses in the API and worker's `TARGETS_JSON` deployment variable. Example shape: `{"https://staging.example.com":["<actual-IP>"]}`. Replace the placeholder with the deployment's real address; do not copy it literally.
- Provide credential variables only to the worker, named `DYNAGUARD_TEST_*`. The fixture password reference is retained for the demo.
- Give the worker network access to that staging target through an appropriate restricted runner/network configuration. Do not remove all network isolation or connect it to unrelated management services.
- Match the origin and complete IP-pin set in the UI JSON. The worker revalidates them before execution.
- Use trusted staging TLS certificates. Certificate/hostname verification stays enabled; there is no insecure TLS switch.
- For explicitly owned local/private targets, set `allow_private: true`. Link-local/cloud-metadata, multicast and unspecified addresses remain prohibited.

The standalone CLI uses your locally reviewed JSON as its scope policy; it does not read the dashboard registry. CDN address changes require a deliberate pin update.

### Optional live-page browser discovery

Install in your activated CLI environment:

```bash
python -m pip install -e './backend[browser]'
python -m playwright install chromium
```

Set `discovery_identity` and `discovery_paths` in the JSON. Include the exact needed page, asset and API paths in `allowed_paths`; an entry ending in `/` permits descendants of that prefix. Avoid granting `/` unless you intend to permit every path on that origin.

```bash
dynaguard discover --config dynaguard.json --output discovery.json
```

For a containerized browser worker:

```bash
docker compose -f compose.yaml -f compose.browser.yaml up --build -d
```

This optional image is larger and needs browser dependencies and more memory. Its default network is still fixture-only. A trusted deployment can instead set `DYNAGUARD_CHROMIUM_EXECUTABLE` to an installed compatible Chrome/Chromium executable.

Discovery renders configured pages and captures JavaScript-initiated GET/HEAD requests through the scoped transport. It does not click buttons, submit forms, follow discovered links automatically or perform write requests. WebSockets and service workers are disabled. Blocked/missing assets and navigation failures yield incomplete coverage. SPA flows requiring localStorage auth state, OAuth redirects or interactive MFA need a future authentication adapter.

Browser routing is not an operating-system sandbox. Use a dedicated restricted runner for untrusted applications. Do not publish the current internal pilot as a public scanning service.

## How to configure tests

See [configuration guide](docs/CONFIGURATION.md) and [system logic](docs/SYSTEM_LOGIC.md).

A permission test contains:

- An authenticated identity that should have access.
- Another identity (or anonymous user) that should not have access.
- A resource URL and nonempty JSON-field assertions identifying a **synthetic** protected record.
- Identity health checks to distinguish a permission denial from an expired session.

A confirmed bypass requires the unauthorized response to match the configured protected-resource assertions. An HTTP 200 alone is never enough. A source-pattern match is never labeled a confirmed runtime bypass.

## Repository layout

```text
backend/dynaguard/       Shared CLI, configuration, transport, verification, source and browser modules
backend/app/            Dashboard API, persistence and background workers
backend/migrations/     Existing fixture schema plus shared-engine run migration
backend/tests/          Legacy and shared-engine acceptance tests
backend/fixture/        Local synthetic application
dashboard/app/         Next.js dashboard and shared-engine panel
examples/               Example data-only configuration
docs/                   System logic, configuration and historical setup
```

## Verification

From an activated environment with backend dependencies installed:

```bash
cd backend
python -m unittest discover -s tests -v
python -m alembic upgrade head
python -m alembic check
```

Run migrations only against your intended local/test database. For browser integration tests, install Chromium and set `DYNAGUARD_BROWSER_TEST=1` before running the suite. That test starts a separate local HTTP application with different routes/login fields, renders its JavaScript page, and checks captured authenticated API traffic.

```bash
cd dashboard
npm ci
npm run build
npm run typecheck
```

See [current verification record](docs/VERIFICATION_SHARED_ENGINE.md) for what was independently run and what remains unverified. The root `VERIFICATION.md` describes the earlier fixture milestone.

## Next implementation steps

1. Validate the browser worker and container networking in your deployment.
2. Connect DynaFlow staging and define its real roles/resources without changing engine code.
3. Add guided authentication/configuration forms and linked dashboard retests.
4. Integrate mature source/dependency scanners and authenticated ZAP scanning.
5. Add dedicated database, workflow and mobile adapters with appropriate test fixtures.

There is no “bypass all security” mode. Each new capability must have an explicit contract, a vulnerable fixture, a secure counterpart and inspectable evidence.
