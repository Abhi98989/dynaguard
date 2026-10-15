# Shared-engine verification — 14 October 2026

This record applies to the shared-engine implementation branch. It does not assert that DynaFlow, PrayasshPOS, the school system or HamroBuzz were scanned.

## Result

41 tests executed: 40 passed and 1 optional browser integration test skipped. Next.js build/typecheck and SQLite migration checks passed.

## Independently exercised

- Legacy fixture acceptance tests remain passing.
- New engine handles a different JSON login contract (`email`, `passcode`, nested `session.token`), different API routes and nested resource assertions.
- Multiple permission tests produce separate outcomes and a confirmed finding only for the designated unauthorized resource disclosure.
- Real loopback HTTP application: CLI detects the vulnerable case, then passes an unchanged-contract retest after the application guard changes.
- Changed test contract is rejected as a retest.
- Failed authentication, ambiguous HTML login responses, DNS-pin mismatch and exhausted request limits do not produce a passing result.
- HTTPS request construction retains Host and SNI hostname when dialing a pinned IP (mock-transport assertion; not a live TLS handshake test).
- Cookie-login transport retains the original hostname for Domain/Secure cookie matching (mock transport).
- Source review masks literal secrets, skips symlinks and marks an empty eligible source set incomplete.
- HTML report export escapes embedded markup.
- Dashboard API queues the shared engine, persists multiple executions/findings, rejects unregistered pins/service-secret references and supports queued and running cancellation.
- Source upload rejects parent-directory traversal and omits matched secrets from saved reports.
- SQLite migration 0002 upgrade, downgrade to 0001, re-upgrade and Alembic metadata checks pass.
- Next.js production build and standalone TypeScript check pass.

## Not independently verified here

- Browser rendering integration: the optional test is present but skipped because the Chromium download returned an invalid archive in this environment. Discovery returns incomplete when the browser cannot launch. Do not treat the browser feature as deployment-validated until the opt-in test passes.
- New browser Docker image and full Compose/PostgreSQL runtime were not executed here.
- Real public HTTPS endpoints, OAuth/MFA, production workloads and any customer's data were not accessed.
- The legacy root VERIFICATION.md records earlier checks by the previous implementation; those broader deployment claims are not newly certified by this update.

## Reproduce

Install backend requirements and `pip install -e 'backend[browser]'`, then run from `backend/`:

```bash
python -m unittest discover -s tests -v
```

For the browser test, first install Chromium, set `DYNAGUARD_BROWSER_TEST=1`, and rerun the suite. You may use a compatible installed browser via `DYNAGUARD_CHROMIUM_EXECUTABLE`.

From `dashboard/`, run `npm ci`, `npm run build`, and `npm run typecheck`.
