# Foundation verification — updated 14 October 2026

## Passed

- **21 backend acceptance tests** in the project virtual environment. Includes actual ASGI vulnerable/fixed fixtures, persistent evidence and hashes, linked retest history, administrator and CSRF checks, cross-project policy rejection, failed login/baseline, unavailable targets, misleading HTTP 200s, protected data in an error response, authentication loss, scope/redirect/DNS blocking, request/body/time limits, nested credential redaction, queued/running cancellation, and abandoned worker leases.
- **Separate-process smoke test**: real loopback HTTP between independently launched FastAPI fixtures, API and worker, using an Alembic-migrated temporary SQLite database. Vulnerable: failed with finding/evidence. Fixed: passed and original finding marked verified fixed. Bad login and unavailable target: incomplete with evidence. Out-of-scope target configuration: rejected. Administrator and fixture credentials absent from reports and captured service logs.
- **Next.js production build**, including TypeScript compilation, and standalone TypeScript check.
- **Headless Microsoft Edge browser acceptance test**: administrator sign-in, project creation, vulnerable/fixed environment configuration, start scan, inspect masked evidence, open finding, run fixed-fixture retest, see verified-fixed result, sign out. No browser page errors. Screenshot: `artifacts/dynaguard-milestone.png`.
- **SQLite migrations**: upgrade, metadata drift check, downgrade to base, upgrade again. No unexpected schema differences.
- **PostgreSQL migration SQL generation** succeeds, including indexes and the retest foreign key. This is a compilation check, not execution against PostgreSQL.
- **Compose configuration** parses successfully.

- **Full Docker Compose / PostgreSQL runtime acceptance**: both application images built successfully after disk space was freed. PostgreSQL migrations executed and `alembic check` reported no schema drift. Requests through the containerized dashboard proxy created a project and environments, ran the vulnerable test with saved finding/evidence, and passed the fixed retest with the original finding marked verified fixed.
- **Deployment failure cases**: stopping the allowed fixture produced an incomplete result with evidence; changing only its synthetic password produced an incomplete login result with masked evidence. An incomplete retest preserved the last conclusive finding lifecycle. An out-of-scope target configuration was rejected.
- **Actual PostgreSQL concurrency**: a separate database connection skipped a locked queued job and claimed the other job; releasing the lock made the first job claimable. Both were claimed once. A cancelled queued job was not claimable.
- **Container restrictions**: inspected worker/fixture containers ran as UID 10001 with read-only root filesystems, all capabilities dropped, no-new-privileges, and no published host ports. Control and fixture networks were internal. These checks validate the configured restrictions, not a penetration test of container isolation.
- **Credential checks**: generated administrator and fixture passwords were absent from captured Compose service logs and scan reports. The invalid-login result also excluded the changed fixture password.
- **Cleanup**: the successful acceptance run removed its own containers, networks, and temporary PostgreSQL volume. Unrelated Docker resources were not removed.
- **Image reuse**: a second complete acceptance run passed with `--skip-build` using stable `dynaguard-backend:local` and `dynaguard-dashboard:local` images. Its disposable resources were also removed.

## Reproduce

The verification script builds images sequentially, handles Docker UTF-8 output on Windows, and stops if disk space falls below 512 MiB. Start with at least 5 GiB free (more if Docker's virtual disk must grow):

```powershell
.\.venv\Scripts\python scripts/compose_smoke.py
```

Use `--skip-build` to reuse the local application images. The check uses port 3000 and an isolated `dynaguard-acceptance-*` Compose project, then removes its own temporary test volume.

## Remaining limits

This verifies the requested local synthetic milestone. DynaFlow and production targets were not accessed. General scanner integrations, production identity/secrets management, and stronger isolation for untrusted scanner code remain outside this milestone; see `README.md` for the deployment boundaries. Earlier disk-space failures were resolved by freeing space before the successful run.
