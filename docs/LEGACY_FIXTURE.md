> Historical fixture-only setup. For the shared engine, start with the root README.

# DynaGuard foundation

An internal, local security-validation pilot for Dynamatrix. This milestone implements one real permission test and its evidence/retest cycle against synthetic fixtures. DynaFlow integration comes later.

## Start with Docker Compose

Prerequisites: Docker Desktop running Linux containers, Docker Compose, Python 3.12+ for the secret-setup helper, and at least 5 GiB free for initial images/build caches (more if Docker needs to grow its virtual disk). Nothing is deployed publicly.

From the project root:

```powershell
python scripts/setup.py
if ($LASTEXITCODE -eq 0) { docker compose up --build -d }
```

The setup helper asks you to choose an administrator password of at least 16 characters. Input is hidden while you type; short or mismatched passwords prompt you to retry. It stores its scrypt hash, plus generated local service secrets, in the ignored `.env` file. It does not print the password. Existing `.env` files are preserved. Once setup has already succeeded, start directly with `docker compose up --build -d`.

Open **http://127.0.0.1:3000**, sign in as **admin**, and use your chosen password. Startup applies the PostgreSQL migration before starting the API or worker. PostgreSQL data persists in a Docker volume.

```powershell
docker compose ps
docker compose logs --tail=50 api worker
docker compose down
```

`down` stops services and retains database records. Fixtures have no host ports. Only the dashboard is published, bound to loopback. If Docker reports a subnet conflict, change both the fixture subnet/static IPs and `TARGETS_JSON` in `compose.yaml` together.

## Walk through the milestone

1. Create a project named `DynaFlow local pilot`.
2. Configure an environment named `Vulnerable fixture`, select `http://fixture-vulnerable:8000`, and enter build identifier `fixture-vulnerable-v1`.
3. Configure a second environment named `Fixed fixture`, select `http://fixture-fixed:8000`, and enter `fixture-fixed-v1`.
4. Start the vulnerable scan. Open its run: the execution should be **failed**, with a **confirmed_bypass** finding. `completed` is the orchestration state, not a passing security result.
5. Open the finding and its masked evidence. The authorized Alice record baseline must succeed, then Bob's designated record and marker must be returned to confirm the bypass.
6. In the finding, select `Fixed fixture` and click **Run retest**. The same test must **pass**: access to Bob's record is denied, and Alice can still access her own record afterward.
7. The original finding becomes **verified fixed**, with the original evidence and retest history retained. Open the JSON report from the run.

Scope: one synthetic ownership boundary. An empty finding list is not a claim that a product is secure. An unavailable target, failed login, lost authentication, unexpected response, exhausted limit, crashed worker, or deadline produces **incomplete**. Cancellation is a separate non-passing result.

## Architecture and data

- `dashboard/`: Next.js App Router + TypeScript. Same-origin API proxy; credentials are not placed in browser storage. Minimal project, environment, run, finding, evidence, and retest views.
- `backend/app/api.py`: FastAPI control plane. Administrator session cookie, CSRF boundary, project/target/policy registration, run requests, reports and cancellation.
- `backend/app/worker.py`: separate process/container, claiming PostgreSQL jobs with row locks and `SKIP LOCKED`. Executes only the fixed test catalog; no supplied scripts or shell commands. No Redis/Celery is needed for this single-test milestone.
- `backend/app/scope.py`: exact origin/path checks, deployment-pinned IPv4 addresses, checks every redirect, connects to the verified IP, disables proxy environment inheritance, bounds requests, response size and duration.
- `backend/app/verification.py`: authorized baseline, cross-owner probe, protected-record assertions and legitimate-access recheck.
- `backend/fixture/main.py`: two synthetic users (`alice`, `bob`), two projects and two designated records. Vulnerable and corrected instances differ only in the ownership guard. No real accounts or services.
- `backend/migrations/`: Alembic initial schema and reversible migration. Models include Project, Environment/allowed target, ScanPolicy, ScanRun, TestExecution, Finding, Evidence and CredentialReference. Each child carries project identity. Retests reference the original finding.

Policies/environments are immutable through the current API. Each run freezes its target, build label, credential reference, test/version and limits. Evidence stores selected, redacted request/response proof fields with timestamps and a SHA-256 integrity hash. It intentionally excludes raw login responses, arbitrary response text and headers. The database stores `fixture/alice`, never the fixture password or access token.

Administrator authentication uses a salted scrypt password hash, an eight-hour signed HttpOnly SameSite=Strict cookie, a login-attempt limit and a custom mutation header with same-origin protections. Cookies use HTTP for loopback development; any future HTTPS deployment must enable `COOKIE_SECURE=true` on the API. The administrator can access all projects in this single-organization pilot.

The trusted worker runs one test at a time. Its cancellation monitor checks about every 100 ms and cancels the active HTTP task, closing the client before acknowledging completion. A test has a default 15-second overall budget, three-second per-request ceiling, eight-request limit and 16 KiB maximum decoded response. An abandoned worker lease is marked incomplete after 40 seconds by a live worker; if all workers are offline, reconciliation happens when one restarts. No automatic test retries.

## Local development without Docker

This fallback uses SQLite and one worker for local debugging. PostgreSQL/Compose is the intended deployment configuration; SQLite does not verify PostgreSQL concurrency or container isolation.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
npm.cmd --prefix dashboard ci
python scripts/setup.py
.\.venv\Scripts\python scripts/dev.py
```

On macOS/Linux, use `.venv/bin/python` and `npm`. The launcher runs migrations, fixtures on `127.0.0.1:8101` / `:8102`, API on `:8000`, worker, and dashboard on `:3000`. Select those loopback targets in the dashboard. Ctrl+C stops the launched processes. Do not run this and Compose on port 3000 simultaneously.

## Verification commands

```powershell
# Acceptance/unit tests (temporary SQLite database; actual ASGI fixtures)
Set-Location backend
..\.venv\Scripts\python -m unittest discover -s tests -v
Set-Location ..

# Separate fixture/API/worker processes, real loopback HTTP, migrated temporary DB
.\.venv\Scripts\python scripts/smoke.py

# Next.js production compilation and TypeScript checks
npm.cmd --prefix dashboard run build
npm.cmd --prefix dashboard run typecheck

# Actual isolated Compose project, PostgreSQL, worker, dashboard proxy
# Uses port 3000; removes only its own dynaguard-acceptance-* test volume afterward.
.\.venv\Scripts\python scripts/compose_smoke.py
```

`scripts/smoke.py --serve` keeps a disposable populated demo at **http://127.0.0.1:3001** for browser QA after a dashboard build. It uses the public synthetic test credential defined in that script, not your development administrator password. Stop it with Ctrl+C. It never modifies `.env` or the development database.

With that disposable demo running, run `npx playwright test` from `dashboard/`. The test uses the installed Microsoft Edge browser, creates a project and environments through the UI, inspects evidence, verifies the fixed retest and signs out. Set `TEST_BROWSER_CHANNEL=chrome` to use an installed Chrome instead. The screenshot is saved under `artifacts/dynaguard-milestone.png`.

The tests cover vulnerable/fixed results, evidence hashes, retest history, failed login, unavailable targets, failed baselines, ambiguous HTTP 200s, authentication expiry, scope/redirect/DNS blocking, limits, masking, administrator/CSRF checks, project-policy boundaries, cancellation and worker loss.

The Compose verification builds images sequentially and stops if free space drops below 512 MiB. It additionally checks actual PostgreSQL job locking, unavailable targets, failed fixture login, queued cancellation, non-root/read-only worker and fixture containers, absence of their host ports, and internal control/fixture networks. With application images already built, `--skip-build` reuses them. Keep the default 5 GiB initial space requirement for fresh builds; `--minimum-free-gib` is intended for retries with cached images/layers. Execution results and any outstanding checks are recorded in `VERIFICATION.md`.

## Remaining boundaries

- This is a local pilot, not a hardened production deployment. No DynaFlow repository or real target has been scanned.
- Only the fixed synthetic permission-test contract is supported. No AI, general scanners, mobile testing, source analysis or arbitrary URL entry.
- The Compose networks isolate fixtures from external routing. The trusted worker still shares a control network and database with the API; a separate scope gateway, restricted database roles, per-run disposable containers and separate runner VM are future hardening work before integrating untrusted tools.
- Local secrets use process environment variables and an ignored `.env`; a managed secret store, evidence encryption/retention/deletion, audit log, backups and multi-user RBAC remain future work.
- Evidence is stored as redacted JSON in PostgreSQL for this small milestone, not object storage. The SHA-256 hash detects content changes when compared but is not a signature against a database administrator.
- Build identifiers are administrator-supplied labels, not independently verified artifact digests. “Verified fixed” applies to the selected retested fixture build, not every environment.
- Session logout clears the browser cookie; there is no server-side session revocation store. Login throttling is in-process. Container images are version-tagged; image-digest pinning and a reviewed dependency-update pipeline remain future work.

Implementation references: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [SQLAlchemy locking/selects](https://docs.sqlalchemy.org/en/20/core/selectable.html). The supplied design plan remains the broader roadmap.
