# Senior QA skill system

DynaGuard's QA extension contains **43 versioned skill contracts and a risk-based planner**. It does not yet contain 43 executable test adapters. Use it to define release coverage and implementation priorities without misrepresenting unexecuted checks as passes.

The catalog is product data in `backend/dynaguard/data/qa_catalog.json`, not a set of installed ChatGPT skills. Both CLI and dashboard call `dynaguard.qa.build_plan`. Existing execution capabilities remain as documented in the root README.

## What a senior QA approach adds

1. Read requirements and resolve ambiguities before declaring behavior correct or defective.
2. Understand users, permissions, business invariants and failure consequences.
3. Prioritize money, privacy, data loss and access boundaries, then lower-risk presentation issues.
4. Test complete outcomes across UI, API and persistence, not only individual HTTP responses.
5. Vary inputs, order, identity, state, timing, connectivity and environment deliberately.
6. Record exact builds, fixture identifiers, seeds and expected/actual outcomes.
7. Investigate failures and classify product defects separately from test or environment failures.
8. Keep flaky, blocked, incomplete, omitted and untested coverage visible.
9. Verify fixes with the original test plus relevant regression checks.
10. Require human observation where usability, accessibility or business acceptance cannot be established automatically.

## CLI

```bash
dynaguard qa catalog --output qa-catalog.json
dynaguard qa plan --profile examples/qa-dynaflow.json --output qa-plan.json
dynaguard report --input qa-plan.json --output qa-plan.html
```

These commands generate a catalog/plan. They do not run the selected tests. Exit code 0 means planning/export succeeded; the plan's release decision remains `not_evaluated` and `executed_checks` remains 0.

The DynaFlow profile is an example specification. Confirm its roles and expected rules with the actual product owner before using it as acceptance criteria.

## Dashboard

Select a project, open **Release QA planning**, inspect the catalog and edit the QA profile JSON. Choose **Create QA plan · does not run tests**. The plan is stored with status `planned` in the project run list, where it can be inspected and downloaded. It is never queued as a live scan.

API routes, protected by the existing administrator checks:

- GET `/qa/skills`
- POST `/projects/{project_id}/qa-plan`

No database migration is needed beyond shared-engine migration 0002. Plans reuse the versioned JSON report storage.

## Profile and applicability

Specify project, build, capabilities and workflows. Each workflow needs a stable ID, name, risk level, roles and nonempty expected business rules. Optional `selected_skills` chooses a subset of applicable skills. Unknown or inapplicable selections are rejected.

Capabilities: web, api, mobile, database, payments, offline, ai, search, files, messaging, hardware, saas. Declare the actual system. A web-only product will not automatically receive printer or mobile-lifecycle checks. Platform-independent skills remain applicable.

The planner orders critical workflows first and records every omitted applicable skill. It lists selected skill contracts with `test_status: not_run`; it generates design tasks, not invented executable test cases or completed test counts.

## Fourteen complementary test-design techniques

| Technique | How to use it |
|---|---|
| Happy path | Verify a representative valid journey and its final state. |
| Negative testing | Reject invalid/missing inputs without unintended side effects. |
| Boundary analysis | Check below, at and above actual business limits. |
| Decision tables | Cover meaningful combinations of role, state and input conditions. |
| State transitions | Check valid, forbidden, repeated and out-of-order changes. |
| Invariants/property-based reasoning | Define domain truths and check them over generated inputs and operation sequences. |
| Pairwise combinations | Reduce large matrices while explicitly adding high-risk combinations. |
| Failure and recovery | Define failure points and expected recovery before injecting faults. |
| Exploratory charters | Time-box investigation and record observations and reproduction steps. |
| Differential testing | Compare versions/implementations against approved fixtures; differences need analysis. |
| Metamorphic testing | Check approved relationships between transformed inputs and outputs. |
| Mutation testing | Change logic in a disposable checkout to measure whether tests detect defects. |
| Bounded fuzzing | Generate structured edge cases with limits, seeds and minimized reproductions. |
| Regression testing | Retain prior failures and cover dependent workflows after changes. |

Not every technique applies to every workflow. For example, financial invariants need exact decimal/rounding rules; a visual comparison requires an approved baseline; mutation testing requires source-level test runners. The planner asks for those prerequisites rather than fabricating them.

## Proposed skill execution contract

A future adapter must provide:

- Skill/test ID and version; supported stacks and capabilities.
- Requirement IDs and business rules.
- Target build/environment and scope policy.
- Named synthetic fixtures and permitted actions.
- Concrete input cases, setup and cleanup.
- Expected assertions with authoritative state checks.
- Time, request/load and impact limits.
- Structured evidence and redaction rules.
- Outcomes: passed, failed, blocked, incomplete, skipped, not_run; retries/flakiness remain visible.
- Reproduction and unchanged-expectation retest instructions.

Do not execute arbitrary shell commands supplied through a QA profile. Future adapters are reviewed code installed by the operator; profile content is data.

## Release assessment policy (specified, not implemented)

A plan cannot determine release readiness. A later assessor must require results for the exact selected build, the required test contracts and evidence provenance.

- Required failures, blocked/incomplete checks, missing results and unresolved flakes prevent a passing decision.
- Unverified findings require triage; scanner severity alone does not prove a defect.
- Skips and exceptions need rationale, an accountable owner and scope visibility; they do not silently become passes.
- Manual acceptance and accessibility review need recorded human observations.
- Results from another build or a weakened test cannot close the original failure.
- A passing assessment must say “passed configured release checks” and show remaining gaps.

## Product-specific starting points

| Product | Highest-priority scenarios |
|---|---|
| DynaFlow | Removed-member access, task/project ownership, attachments, assignment and notifications. |
| School system | School isolation, student privacy, marks and fees, parent/teacher access, offline attendance if supported. |
| PrayasshPOS | Totals and rounding, stock/invoice consistency, refunds, duplicate payments, offline sync and receipt printing. |
| HamroBuzz | Author/editor roles, draft privacy, publishing transitions, uploaded media, caching and public rendering. |
| AI-enabled features | Retrieval evaluation, unsupported answers, user-context isolation and controlled instruction-conflict cases. |

Examples are proposed requirements, not findings about existing products.

## Implementation order

1. Turn approved high-risk workflows into functional/API contracts and fixture-backed tests.
2. Extend existing permission checks and add transaction/idempotency assertions.
3. Integrate browser workflows, accessibility checks and approved visual baselines.
4. Add workload-based performance, recovery, migration/restore and device-specific adapters.
5. Add result provenance, release assessment and guided human acceptance review.

Every executable adapter needs a failing fixture, a correct counterpart and a blocked/incomplete case before it can participate in a release decision. Load, stress, recovery and mutation tests belong in controlled isolated environments with explicit limits.

## References

- OWASP Web Security Testing Guide: https://owasp.org/projects/web-security-testing-guide
- OWASP business-logic testing: https://wstg.owasp.org/stable/4-Web_Application_Security_Testing/10-Business_Logic_Testing/
- Playwright assertions: https://playwright.dev/docs/test-assertions
- Playwright accessibility testing: https://playwright.dev/docs/accessibility-testing
- k6 thresholds: https://grafana.com/docs/k6/latest/using-k6/thresholds/

These references inform the proposed approach. Listing a tool does not mean its adapter is installed or implemented.

## Skill catalog

### Requirements and traceability

ID: `requirements` · Status: **planned** · Environment: local_or_staging

- Resolve ambiguous acceptance criteria
- map requirements to tests
- list uncovered requirements

Evidence: Requirement IDs, approved expected behavior, coverage gaps.

Current execution: No executable adapter for this skill is implemented.

### Risk-based test strategy

ID: `risk` · Status: **planned** · Environment: local_or_staging

- Rank customer and business impact
- prioritize changed components
- identify dependencies and rollback risks

Evidence: Impact rationale, changed components, priorities.

Current execution: No executable adapter for this skill is implemented.

### Source and configuration review

ID: `source` · Status: **partial** · Environment: local_or_staging

- Inspect sensitive literals
- review dangerous code patterns
- distinguish test fixtures from deployed code

Evidence: File and line, rule ID, masked evidence.

Current execution: Seven source heuristics only; no full static analysis or dependency scanning.

### Unit and property-based testing

ID: `unit` · Status: **planned** · Environment: local_or_staging

- Test pure business functions
- test invariants across generated inputs
- check meaningful assertions

Evidence: Test names, seed, minimized counterexample, runner version.

Current execution: No executable adapter for this skill is implemented.

### Component behavior

ID: `component` · Status: **planned** · Environment: local_or_staging

- Exercise loading/empty/error states
- verify input/output behavior
- isolate dependencies

Evidence: State matrix, assertions, component build.

Current execution: No executable adapter for this skill is implemented.

### Service integration

ID: `integration` · Status: **planned** · Environment: local_or_staging

- Verify service boundaries
- test downstream errors
- check contract version compatibility

Evidence: Correlated requests, sandbox responses, integration versions.

Current execution: No executable adapter for this skill is implemented.

### API contract and schema

ID: `api-contract` · Status: **planned** · Environment: local_or_staging

- Validate response schema
- test required/optional fields
- validate status codes and pagination

Evidence: Specification version, endpoint, schema differences.

Current execution: No executable adapter for this skill is implemented.

### Boundary and negative testing

ID: `boundaries` · Status: **planned** · Environment: local_or_staging

- Partition valid/invalid input
- test values just below/at/above limits
- test Unicode/null/empty values

Evidence: Input class, expected behavior, actual output.

Current execution: No executable adapter for this skill is implemented.

### End-to-end business workflows

ID: `workflow` · Status: **planned** · Environment: local_or_staging

- Exercise complete user journeys
- verify persistent side effects
- test interrupted and reversed flows

Evidence: Steps, final business state, fixture IDs.

Current execution: No executable adapter for this skill is implemented.

### Authentication and session lifecycle

ID: `session` · Status: **planned** · Environment: local_or_staging

- Test expiry/revocation/logout
- test password reset lifecycle
- check session behavior after role changes

Evidence: Session lifecycle assertions, masked requests.

Current execution: No executable adapter for this skill is implemented.

### Roles and record ownership

ID: `permissions` · Status: **partial** · Environment: local_or_staging

- Compare authorized and unauthorized identities
- test designated cross-owner records
- check identity health after denial

Evidence: Baseline, probe, matched synthetic fields, role contract.

Current execution: Configured read authorization only; no write-action or general privilege escalation testing.

### Tenant and branch isolation

ID: `tenant` · Status: **partial** · Environment: local_or_staging

- Separate tenant fixtures
- test records and exports
- test shared cache and attachment boundaries

Evidence: Tenant IDs, ownership rule, bounded disclosure proof.

Current execution: Only explicitly configured cross-tenant API reads; cache, exports and attachments need separately configured checks or future adapters.

### Web and API security

ID: `security` · Status: **planned** · Environment: local_or_staging

- Apply relevant OWASP tests
- validate scanner candidates
- distinguish exposure from demonstrated impact

Evidence: Versioned test IDs, redacted proof, scope.

Current execution: No executable adapter for this skill is implemented.

### Business-rule abuse

ID: `business-abuse` · Status: **planned** · Environment: local_or_staging

- Attempt skipped approvals
- test invalid state transitions
- test inconsistent combinations of otherwise valid inputs

Evidence: Business rule, transition history, synthetic side effects.

Current execution: No executable adapter for this skill is implemented.

### Database integrity

ID: `database` · Status: **planned** · Environment: local_or_staging

- Check constraints and relationships
- test transaction rollback
- detect orphan or inconsistent records

Evidence: Before/after queries on fixtures, constraint assertions.

Current execution: No executable adapter for this skill is implemented.

### Migration and rollback

ID: `migration` · Status: **planned** · Environment: isolated_copy

- Test upgrades from supported versions
- check data preservation
- rehearse rollback or roll-forward recovery

Evidence: Migration versions, reconciliation totals, restore result.

Current execution: No executable adapter for this skill is implemented.

### Concurrency and race conditions

ID: `concurrency` · Status: **planned** · Environment: isolated_copy

- Synchronize competing updates
- test stock/seat allocation
- check lost updates and locking behavior

Evidence: Controlled schedule, invariants, counts before/after.

Current execution: No executable adapter for this skill is implemented.

### Duplicate and replay handling

ID: `idempotency` · Status: **planned** · Environment: local_or_staging

- Repeat requests with same operation identity
- retry after timeout
- check delayed duplicate events

Evidence: Operation IDs, side-effect counts, deduplication outcome.

Current execution: No executable adapter for this skill is implemented.

### Expected-load performance

ID: `performance` · Status: **planned** · Environment: local_or_staging

- Measure agreed workload
- assert latency/error-rate thresholds
- detect regressions against a comparable baseline

Evidence: Workload, p95/p99, error rate, resource metrics.

Current execution: No executable adapter for this skill is implemented.

### Stress and spike behavior

ID: `stress` · Status: **planned** · Environment: isolated_copy

- Increase load in isolated capacity tests
- enforce stop conditions
- verify recovery after bursts

Evidence: Load profile, abort threshold, saturation and recovery metrics.

Current execution: No executable adapter for this skill is implemented.

### Soak and resource stability

ID: `soak` · Status: **planned** · Environment: isolated_copy

- Run sustained representative activity
- observe memory/connection growth
- check queue accumulation

Evidence: Duration, resource trend, backlog, recovery.

Current execution: No executable adapter for this skill is implemented.

### Fault injection and graceful recovery

ID: `resilience` · Status: **planned** · Environment: isolated_copy

- Simulate dependency timeout/unavailability
- inspect compensation
- verify bounded retries and useful errors

Evidence: Injected fault, expected degradation, recovery evidence.

Current execution: No executable adapter for this skill is implemented.

### Offline sync and conflict resolution

ID: `offline` · Status: **planned** · Environment: local_or_staging

- Disconnect and reconnect
- reorder queued changes
- test conflicting edits and repeated sync

Evidence: Queue state, conflict policy, final reconciled records.

Current execution: No executable adapter for this skill is implemented.

### Accessibility

ID: `accessibility` · Status: **planned** · Environment: local_or_staging

- Run automated accessibility checks
- test keyboard/focus
- review screen-reader and error announcements

Evidence: Rule violations plus manual keyboard/screen-reader observations.

Current execution: No executable adapter for this skill is implemented.

### Visual regression

ID: `visual` · Status: **planned** · Environment: local_or_staging

- Compare approved baselines
- stabilize fonts/time/data
- investigate differences instead of auto-accepting

Evidence: Baseline ID, viewport, diff, reviewer decision.

Current execution: No executable adapter for this skill is implemented.

### Responsive layout

ID: `responsive` · Status: **planned** · Environment: local_or_staging

- Exercise small/large viewports
- test zoom and long text
- check navigation and overflow

Evidence: Viewport matrix, clipping/focus observations.

Current execution: No executable adapter for this skill is implemented.

### Browser and operating-system compatibility

ID: `compatibility` · Status: **planned** · Environment: local_or_staging

- Run priority workflows on supported combinations
- compare storage/download behavior
- check platform-specific failures

Evidence: Browser/OS versions and per-flow outcomes.

Current execution: No executable adapter for this skill is implemented.

### Mobile lifecycle and permissions

ID: `mobile` · Status: **planned** · Environment: local_or_staging

- Test denied/revoked permissions
- background/resume/process death
- deep links and notification entry points

Evidence: Device/OS, lifecycle sequence, observed state.

Current execution: No executable adapter for this skill is implemented.

### Localization and date/time correctness

ID: `localization` · Status: **planned** · Environment: local_or_staging

- Test Nepali/English and Unicode
- validate timezone/currency/rounding
- inspect long text and calendar boundaries

Evidence: Locale/timezone, reference calculations, formatting assertions.

Current execution: No executable adapter for this skill is implemented.

### Notifications and integrations

ID: `messaging` · Status: **planned** · Environment: local_or_staging

- Test recipient/tenant routing
- duplicate/delayed delivery
- revoked subscriptions and provider failures

Evidence: Sandbox recipient IDs, event IDs, delivery assertions.

Current execution: No executable adapter for this skill is implemented.

### Payments and financial correctness

ID: `finance` · Status: **planned** · Environment: local_or_staging

- Reconcile totals/tax/discount/rounding
- test pending/failed/reversed payments
- verify refunds and ledger consistency

Evidence: Sandbox transaction IDs, expected calculations, reconciliation.

Current execution: No executable adapter for this skill is implemented.

### Files, uploads and exports

ID: `files` · Status: **planned** · Environment: local_or_staging

- Validate type/size/ownership
- test corrupted and large fixtures
- verify export encoding and download permissions

Evidence: File digest, limits, authorization evidence.

Current execution: No executable adapter for this skill is implemented.

### Search, filtering and reports

ID: `search` · Status: **planned** · Environment: local_or_staging

- Compare aggregates with known dataset
- test pagination/filter combinations
- verify sorting and access filtering

Evidence: Seed dataset, expected totals, query/filter parameters.

Current execution: No executable adapter for this skill is implemented.

### Privacy and data lifecycle

ID: `privacy` · Status: **planned** · Environment: local_or_staging

- Inspect logs and responses for sensitive fields
- test configured retention/deletion
- review unnecessary collection

Evidence: Masked field observations, deletion verification, retention policy.

Current execution: No executable adapter for this skill is implemented.

### Logging and operational diagnosis

ID: `observability` · Status: **planned** · Environment: local_or_staging

- Correlate request and error events
- verify actionable alerts
- check redaction and audit completeness

Evidence: Correlation IDs, test alert, redaction assertions.

Current execution: No executable adapter for this skill is implemented.

### Deployment and configuration

ID: `deployment` · Status: **planned** · Environment: local_or_staging

- Test startup/health/readiness
- check environment separation
- detect debug settings and missing configuration

Evidence: Build digest, environment checks, health assertions.

Current execution: No executable adapter for this skill is implemented.

### Backup and restore

ID: `backup` · Status: **planned** · Environment: isolated_copy

- Restore to an isolated environment
- verify record integrity
- measure recovery against agreed objectives

Evidence: Backup ID, restore log, reconciliation, measured recovery.

Current execution: No executable adapter for this skill is implemented.

### Exploratory and usability review

ID: `exploratory` · Status: **planned** · Environment: local_or_staging

- Time-box risk-focused charters
- investigate unexpected behavior
- review user confusion and recovery paths

Evidence: Charter, session notes, reproducible findings, human reviewer.

Current execution: No executable adapter for this skill is implemented.

### Regression and change-impact review

ID: `regression` · Status: **planned** · Environment: local_or_staging

- Retest repaired defects
- cover dependent workflows
- retain flaky evidence and broaden when impact is uncertain

Evidence: Changed areas, selected tests, historical comparison.

Current execution: No executable adapter for this skill is implemented.

### User acceptance testing

ID: `uat` · Status: **planned** · Environment: local_or_staging

- Have representative users complete real tasks
- validate business expectations
- record unresolved acceptance gaps

Evidence: Named reviewer, task observations, acceptance decisions.

Current execution: No executable adapter for this skill is implemented.

### AI feature quality and isolation

ID: `ai` · Status: **planned** · Environment: local_or_staging

- Test retrieval correctness and unsupported claims
- check cross-user context separation
- use controlled prompt-injection fixtures

Evidence: Versioned evaluation set, model/config IDs, graded evidence.

Current execution: No executable adapter for this skill is implemented.

### Dependency and supply-chain review

ID: `supply-chain` · Status: **planned** · Environment: local_or_staging

- Match dependencies to advisories
- inspect lockfiles and provenance
- assess deployability and reachability

Evidence: Package/version, advisory, supported ecosystem, confidence.

Current execution: No executable adapter for this skill is implemented.

### Printers and external devices

ID: `hardware` · Status: **planned** · Environment: local_or_staging

- Test disconnect/reconnect
- verify print content and duplicate prevention
- test device-specific errors

Evidence: Device/firmware, print-job IDs, observed output.

Current execution: No executable adapter for this skill is implemented.
