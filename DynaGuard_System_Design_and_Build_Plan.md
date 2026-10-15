# DynaGuard — Security Validation Platform
## Proposed implementation plan • 13 October 2026
Prepared for Abhishek Chaudhary / Dynamatrix Solution. Working name only.

## 1. Goal and boundaries
Build an internal platform to discover weaknesses, demonstrate specific security failures in authorized test environments, explain the cause, propose repairs, and retest. Cover source code, web/API behavior, database policy, mobile builds, infrastructure configuration and selected functional workflows.

This is a design proposal, not a completed audit. No product has been scanned. Technology stacks and deployments of individual products must be inventoried before implementing adapters. No universal scanner can guarantee security or verify every function. Show unknown coverage explicitly.

Start single-organization, with multiple projects. Do not begin with a public service where arbitrary users submit targets.

## 2. Product requirements
- Register products, repositories, commits, deployment builds, environments and owners.
- Supply API specifications, role matrices, synthetic fixtures and business rules.
- Run repeatable scan profiles, collect evidence and compare findings over time.
- Distinguish suspicion, exposure, reproduced bypass and demonstrated impact.
- Show security, functional correctness and architecture review as separate categories.
- Link evidence to the exact target build and test version.
- Propose repairs; changes remain reviewable branches or patches, with no automatic production deployment.
- Export developer-readable Markdown/JSON initially; add HTML/PDF and SARIF integrations later.
- Maintain an explicit list of unsupported or untested components.

## 3. Architecture
Control plane:
- Next.js/TypeScript dashboard.
- FastAPI application API, project registry, policy service and scan coordinator.
- PostgreSQL for configuration, scan state, test outcomes, findings and audit events.
- Redis/Celery for initial asynchronous work dispatch; PostgreSQL remains the source of truth.
- Private encrypted object storage for redacted evidence and reports.
- Secret manager for short-lived test credentials; database stores references, not plaintext values.

Execution plane:
- Separate worker host/VM from the dashboard and production workloads.
- Disposable restricted containers per run, with CPU, memory, disk and duration limits.
- Dedicated browser/API workers, source-scanning workers and later mobile workers.
- A scope-enforcing network gateway through which active test traffic must pass.
- Separate controlled access for scanner update feeds; target traffic cannot use unrestricted egress.
- Workers receive only run-specific credentials and cannot read other projects' secrets.

AI service:
- Receives minimized, redacted code context and evidence.
- Proposes typed test plans and explains results.
- Does not execute arbitrary shell commands or change target scope.
- Generated tests require validation and sandbox trial before being eligible for execution.
- Repository comments, pages, logs and scanner output are untrusted data, not instructions.

Prefer a modular monolith for the control plane. Avoid unnecessary microservices and Kubernetes in the pilot.

## 4. End-to-end run
1. Register assets and exact permitted hosts, ports and environments.
2. Freeze commit SHA, build identifier, scanner versions, rule versions and scan policy.
3. Preflight: validate target scope, staging health, test-account login and fixture ownership.
4. Discover routes from OpenAPI, source and authenticated navigation; reconcile differences.
5. Build a coverage manifest: route × role × ownership context × selected test type.
6. Execute source, dependency, secret and configuration scans.
7. Execute selected browser/API security and functional test cases.
8. Verify candidate findings using controlled records and minimum sufficient proof.
9. Normalize, redact, deduplicate and retain evidence.
10. Generate impact, cause, repair guidance and retest instructions.
11. Clean up fixtures and verify cleanup; flag failures for intervention.
12. Retest after a fix and compare against the original finding.

Run states: queued, preflight, running, verifying, reporting, completed, partial, failed, cancelled. A scanner crash or expired login is an incomplete scan, never a clean result. Cancellation must stop running worker processes and network access, not just remove queued tasks.

Use idempotent orchestration and worker leases. Never automatically retry a state-changing test unless its fixture and side effects have been reconciled.

## 5. What to integrate and what to build
| Capability | Initial choice | Custom work |
|---|---|---|
| Source patterns | Semgrep | Stack-specific rules, result normalization, coverage reporting |
| Dependency and container/config checks | Trivy | Lockfile support checks, freshness tracking, attribution |
| Secret detection | Gitleaks plus delivered-artifact inspection | Masking, contextual classification, deduplication |
| Running web/API security | ZAP Automation Framework | Auth setup, scoped policies, alert verification |
| Role and workflow validation | Playwright plus custom API tests | Role matrix, fixture ownership, assertions and cleanup |
| Database policy review | Read-only schema/config exports and scoped adapters | PostgreSQL/MongoDB/Firebase/Supabase packs only when relevant |
| Flutter/mobile | Source and backend checks first; MobSF later | Android fixtures, platform-specific tests, declared limitations |
| Architecture review | Dependency map and AI-assisted review | Trust boundaries, retries, transactional rules, human validation |

These are proposed integrations, not claims that one tool fully supports every stack. Validate current licenses, supported languages/lockfiles, features, telemetry settings and commercial restrictions before packaging or selling integrations. Pin versions and update through a test pipeline. A detected vulnerable dependency is not automatically proof of runtime exploitability.

Use OWASP ASVS for web/API requirements, WSTG for testing methods, and MASVS/MASTG for mobile. Store versioned requirement identifiers; do not claim certification.

## 6. Test-engine contract
Every test definition must contain:
- Stable test ID, version, category and applicable stack.
- Required environment and permitted impact class.
- Roles, credentials references and fixture prerequisites.
- Baseline expected success for an authorized user.
- Unauthorized or malformed action being tested.
- Expected denial or safe behavior.
- Explicit observable evidence required for failure.
- Request/time limits, cancellation and cleanup steps.
- Regression test and relevant requirement reference.

Do not equate HTTP 200 with a bypass: the response may be a login page or denial object. Confirm the protected data or intended state change. A legitimate baseline must succeed before an authorization test is meaningful. Distinguish authentication expiry from a successful security control.

For a role test, create two synthetic users and separately owned synthetic records, perform the expected authorized request, then test the disallowed access and inspect only the designated record. Do not enumerate real customer data.

For a leaked secret, classify exposure independently from validity. Public IDs and client configuration keys are not automatically secrets. Never reuse discovered real credentials for exploration; mask them and recommend rotation when appropriate.

## 7. Scan profiles
A. Repository review: static code, history secrets, dependencies, configuration. Repository installation/build scripts do not run automatically.
B. Production observation: inspection of approved pages and delivered assets with bounded requests. Even browsing can have side effects; exclude state-changing flows.
C. Staging validation: authenticated tests and controlled security probes against synthetic records.
D. Isolated deep tests: concurrency, recovery, replay and destructive workflow simulation only in a disposable copy with explicit policy.

An administrator configures scope and profile once; routine runs follow that stored policy. New scope or higher impact needs a policy update, not a repeated prompt for each ordinary test. This plan does not authorize any live scan.

## 8. Scope and isolation controls
- Exact host/port/environment allowlists; validate resolved addresses and every redirect.
- Block arbitrary external targets, cloud metadata, internal management interfaces and the platform itself. Explicit internal staging addresses are permitted only through a dedicated configured runner.
- Enforce boundaries at network level as well as application level, including DNS rebinding defenses.
- Deny cross-origin credential forwarding and prevent outbound callbacks to unrelated services.
- Disable real payment, email, SMS and notification side effects in staging; use local sinks or provider sandboxes.
- Global and per-project rate limits, time limits, health-based stop conditions and emergency cancellation.
- No persistence, credential spraying, unrestricted network pivoting, real-data dumping or availability attacks in the initial platform.
- Use isolated workers with non-root execution, read-only filesystems where feasible, no host Docker socket and no broad host mounts.
- Treat malicious repositories/build scripts as untrusted execution; use stronger VM isolation before accepting externally supplied repositories.

## 9. Evidence and reporting model
Record each finding with project, environment, build/commit, test ID, scanner version, first/last seen, category, severity, confidence, verification state, affected asset, preconditions, expected/actual behavior, redacted request/response, fixture references, source location, cause, recommendation, owner and retest history.

Verification states:
- Suspected weakness: static or heuristic evidence only.
- Confirmed exposure: sensitive material observed.
- Confirmed bypass: unauthorized action demonstrated.
- Confirmed impact: designated test data accessed or changed.
- Inconclusive: missing prerequisites or ambiguous result.

Lifecycle states are separate: open, triaged, in progress, fixed pending retest, verified fixed, accepted risk, false positive. Accepted risks and suppressions require an owner, reason and review date.

Evidence must be redacted before routine persistence, logs and AI transmission. Retain hashes, timestamps and tool/test versions for traceability. Restrict report access because masked findings still reveal weaknesses. Provisional retention: redacted evidence 30 days, summaries 180 days; make these configurable and support deletion. Use private short-lived download links.

Example report wording:
“Cashier test account refunded synthetic transaction T-100 without manager authorization. The authorized manager baseline succeeded. The server accepted the cashier request and the fixture state changed. Missing server-side refund permission check is suspected from source review; confirm the exact cause before merging a repair.”
A demonstrated API bypass must not be labeled a complete server takeover.

## 10. Database and functional review
Database checks:
- Review roles, exposed access paths, schema/migrations, access policies and storage permissions.
- Prefer metadata exports or dedicated read-only accounts; no production superuser credential.
- Test tenant/owner isolation through APIs and directly only where the application legitimately exposes a database client API.
- Inspect constraints, indexes and query patterns; performance findings need measured workload evidence.
- Test transactions, duplicate protection and race conditions in staging.
- Verify backup restoration in an isolated environment; merely finding a backup does not establish recoverability.

Functional and design checks:
- Explicit assertions for workflow transitions, money and inventory invariants.
- Expected retry behavior, failure compensation and idempotency.
- Cache/session invalidation and permissions after user removal.
- Offline synchronization scenarios where supported.
- Design concerns are hypotheses until supported by a failing test, observed behavior or human review.

## 11. Per-product test packs
DynaFlow pilot:
- Roles: actual administrator, lead and member definitions after inventory.
- Membership, project/task ownership, attachments, reassignment, removed-member access.
- Synthetic projects for two teams and a few fixtures per role.

School system:
- Actual school/branch boundaries and administrator/teacher/parent/student permissions.
- Marks, attendance, student data, fees, documents and approval workflows.
- Android app/API access and offline synchronization if implemented.

PrayasshPOS:
- Actual owner/manager/cashier/branch rules.
- Discounts, refunds, price authority, stock, invoice uniqueness, transaction replay.
- Sandboxed payments and offline-sync/concurrency scenarios if present.

HamroBuzz:
- Actual author/editor/admin workflow.
- Draft visibility, publishing approval, content rendering, uploads, admin sessions and public cache behavior.

Four mini projects:
- Run inventory and common scan pack first.
- Assign relevant authentication, database, upload and workflow packs individually.

These are proposed cases; do not assume roles or features exist without inspecting each product.

## 12. Data entities and API outline
Core entities:
Project, Environment, Asset, RepositorySnapshot, RoleProfile, CredentialReference, FixtureSet, BusinessRule, TestDefinition, ScanPolicy, ScanRun, TestExecution, Finding, EvidenceArtifact, Retest, RiskAcceptance, AuditEvent.

Every child record carries project identity; server-side access checks apply to reads, writes and downloads. Findings are fingerprinted using rule/test, asset and stable code context, not volatile line number alone.

Suggested APIs:
- POST /projects and /projects/{id}/environments
- POST /projects/{id}/assets and /projects/{id}/policies
- POST /projects/{id}/scan-runs
- GET /scan-runs/{id} and /scan-runs/{id}/coverage
- POST /scan-runs/{id}/cancel
- GET /projects/{id}/findings
- POST /findings/{id}/retests
- GET /scan-runs/{id}/report

Validate all submitted paths, URLs, archives and scanner arguments. Users select approved test IDs; they do not submit arbitrary worker shell commands.

## 13. Dashboard
- Portfolio: critical/high confirmed findings, unverified risks, last scan build and incomplete coverage by product.
- Project: assets, environments, roles, business rules, scans and remediation.
- Run: current stage, executed/skipped/failed tests, authentication health, stop button.
- Finding: evidence, cause, suggested repair, owner and retest.
- Coverage: route/role/business-rule matrix, source coverage and unsupported components.
- Settings: scope policy, test credentials, evidence access and retention.

Avoid a single “security percentage.” Compare products only with scope, coverage and recency visible.

## 14. Delivery roadmap
Planning estimate: 2 engineers substantially dedicated, security reviewer at milestones, prepared staging environments. Approximately 12–16 weeks for a useful internal v1; substantially longer for comprehensive mobile coverage or a public multi-tenant service. This is an estimate, not a delivery commitment.

Weeks 1–2: inventory, staging fixtures, threat model, role specifications, lab cases and acceptance criteria.
Weeks 3–4: registry, policies, isolated workers, job state, cancellation, secrets and basic dashboard.
Weeks 5–6: source/dependency/secret adapters and normalized evidence reports. Repository-only MVP.
Weeks 7–9: authenticated API/browser tests, ZAP adapter, DynaFlow permission and workflow checks.
Weeks 10–12: school/POS/news packs, database review, repairs/retests and CI integration.
Weeks 13–16: Android build analysis, stabilization, benchmark improvements, access review and internal rollout.

Ship incrementally after each gate; do not postpone auditing existing products until the whole platform is complete.

## 15. Acceptance gates
- Seed known vulnerabilities in disposable lab applications; maintain secure counterpart cases.
- Report detection and false-positive rates per supported test class on a held-out fixture set.
- All “confirmed bypass” results include authorized baseline, failing rule assertion and inspectable evidence.
- Scope tests prove redirects, DNS changes and embedded links cannot escape allowed targets.
- Authentication loss, parser failure, unsupported languages and scanner crashes produce incomplete statuses.
- Cancellation demonstrably kills active work and network access within a defined operational target.
- Secret masking passes fixtures before logs, storage and AI use.
- Two synthetic tenants/projects cannot access each other's dashboard records, credentials or evidence.
- Cleanup verified; state-changing retries do not duplicate effects.
- Known fixed fixtures pass retests while originally vulnerable fixtures still fail.
- Security reviewer evaluates a representative set of confirmed and dismissed findings before relying on release gates.

Initial CI: source/dependency/secret checks on pull requests; deeper staging checks on selected builds. Fail release gates on agreed new confirmed findings, confirmed secret exposures and required tests that did not complete. Treat unverified high-impact alerts as review-required. Do not silently pass incomplete required scans.

## 16. Resources and onboarding checklist
People: backend/security automation engineer, frontend/full-stack engineer, product owner/domain expert; periodic experienced security review.
Infrastructure: separate control and runner environments, PostgreSQL, queue, private evidence storage, secret manager, staging copies and synthetic fixtures.
Pilot sizing hypothesis: modest control server (about 2–4 vCPU, 4–8 GB RAM) plus a separate 4–8 vCPU/16 GB runner for low concurrency. Measure real usage before buying; mobile emulators need additional resources. No GPU is required when using hosted AI. iOS work needs suitable Apple build/test infrastructure.
Budget categories: compute, evidence storage/backups, LLM usage caps, any scanner licensing, engineering and independent review. Obtain actual provider quotes after sizing.

For every product collect:
- Repository access or sanitized ZIP; ZIP cannot provide full Git-history coverage.
- Frameworks, package managers, databases, hosting and build instructions.
- Staging URL/API specifications and exact target scope.
- Role matrix and dedicated credentials supplied through the secret manager.
- Two isolated organizations/owners where relevant and synthetic fixtures.
- Critical workflow expectations and prohibited side effects.
- Deployment commit/build identifiers; sanitized configuration/schema exports.
- Android build initially; iOS scope later.
- Restore/reset method and designated technical owner.

Immediate implementation backlog: inventory DynaFlow, define 10 meaningful role/workflow tests, create vulnerable and secure fixtures, implement scope gateway and one isolated worker, integrate the first repository scanners, then add authenticated evidence-backed verification.

## 17. Reference documentation
Checked 13 October 2026. Tool capabilities and licensing must be rechecked when integrating.
- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- OWASP WSTG: https://owasp.org/projects/web-security-testing-guide
- OWASP MASVS/MASTG: https://mas.owasp.org/
- ZAP Automation Framework: https://www.zaproxy.org/docs/automate/automation-framework/
- Semgrep language support: https://docs.semgrep.dev/supported-languages/
- Trivy configuration scanning: https://trivy.dev/docs/latest/scanner/misconfiguration/
- Gitleaks: https://gitleaks.org/
- Playwright API tests: https://playwright.dev/docs/api-testing
- MobSF: https://github.com/MobSF/Mobile-Security-Framework-MobSF

