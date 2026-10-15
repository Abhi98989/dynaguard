# Project configuration

Version 1 is strict JSON. Unknown fields are rejected so typos do not silently disable checks. `dynaguard init` creates a starter and never overwrites an existing configuration.

## Top-level fields

| Field | Meaning |
|---|---|
| version | Must be 1 |
| project | Stable project name |
| build_id | Operator-supplied build label; not verified against an artifact |
| target | One exact HTTP(S) origin, IP pins and allowed paths |
| identities | Named authentication profiles |
| tests | Up to 100 configured read-permission assertions |
| limits | Global request, time, response-body and page limits |
| discovery_paths | Explicit pages to render; discovered links are not automatically followed |
| discovery_identity | Identity used for rendered-page requests |

The engine supports a single origin per configuration. For separate frontend and API origins, create separate configurations for now. Cross-origin assets are blocked and reported; multi-origin support is future work.

## Target

```json
{
  "origin": "https://staging.example.com",
  "pinned_ips": ["203.0.113.10"],
  "allowed_paths": ["/auth/session", "/api/me", "/api/items/", "/app", "/assets/"],
  "allow_private": true
}
```

The address above is documentation-only and must be replaced. `allow_private` permits explicitly pinned non-global addresses; it does not permit link-local, multicast or unspecified addresses. Public targets should normally use `false`.

Paths are exact unless they end in `/`, in which case descendants are permitted. Query strings are supported in requested resources but omitted from persisted request-path evidence. Encoded/ambiguous paths are intentionally unsupported in this version. Origins cannot contain credentials, query strings, fragments or a non-root path.

Each request resolves DNS and requires all returned addresses to match the permitted pins. The connection uses a validated address. HTTPS retains the original hostname for Host, SNI and certificate verification. Redirects remain in the same allowed origin/path scope. Non-GET login redirects are unsupported and yield incomplete results.

## Identities

Anonymous:

```json
{"kind": "anonymous"}
```

Existing bearer credential:

```json
{
  "kind": "bearer",
  "token_env": "DYNAGUARD_TEST_MEMBER_TOKEN",
  "auth_check": {"path": "/api/me", "expected": {"user.id": "test-member"}}
}
```

JSON login with custom field names:

```json
{
  "kind": "json_login",
  "login_path": "/auth/session",
  "username": "member@example.test",
  "username_field": "email",
  "password_field": "passcode",
  "password_env": "DYNAGUARD_TEST_MEMBER_PASSWORD",
  "session": "bearer",
  "token_field": "session.token",
  "auth_check": {"path": "/api/me", "expected": {"user.id": "test-member"}}
}
```

For cookie login, use `"session": "cookie"`; token_field is unused. The login response must currently return HTTP 200. Cookie matching uses the original target hostname even when the actual connection is pinned to an IP. Separate identities have separate cookie jars. Cookie-based auth is tested by the mandatory identity health check.

All authenticated identities require a health check. Dotted assertion keys address nested JSON objects; array selectors are unsupported. Comparisons are type-sensitive. Use stable synthetic identifiers, not real personal records or secrets, in assertions.

Dashboard worker environment references must start with `DYNAGUARD_TEST_`, except the legacy `FIXTURE_PASSWORD`. This prevents selecting a service credential such as SESSION_SECRET through the UI. The CLI runs under your local configuration and environment; it has no server credential registry.

## Read-permission tests

```json
{
  "id": "projects.member-boundary",
  "title": "Member can access another team's synthetic project",
  "authorized_identity": "team-b-owner",
  "probe_identity": "team-a-member",
  "resource": {
    "path": "/api/projects/synthetic-project-b",
    "expected": {"project.id": "synthetic-project-b", "project.marker": "audit-only-942"}
  },
  "severity": "high",
  "recommendation": "Check membership and ownership on the server before returning the project."
}
```

Both identity names must exist and must differ. The authorized baseline cannot be anonymous. The resource assertions must be nonempty. Broad assertions such as `success: true` are weak evidence: choose values uniquely identifying the protected synthetic resource.

Possible outcomes:

- **failed / confirmed_bypass:** the unauthorized response matches the protected-resource assertions, even if its status is an error.
- **passed:** the authorized baseline succeeds, the probe receives 403/404 (or 401 for anonymous), and authenticated identities still pass their health checks.
- **incomplete:** login failure, stale session, missing credentials, unexpected response, exhausted budget, network error, denied scope or missing prerequisites.

The test does not identify the precise code defect. It demonstrates an authorization boundary failure. A recommendation is configured guidance, not an automatically validated patch.

## Limits

Defaults: 100 requests, 120 seconds, 1 MiB per decoded response and 10 pages. Limits are shared across tests/identities in a run. Maxima: 1000 requests, 600 seconds, 4 MiB per response and 50 pages. Requests have an additional five-second ceiling. No state-changing retries are performed.

## Reports and retention

The engine records status, assertion outcomes, selected paths, test-contract hashes and coverage. It omits response bodies, authorization headers, passwords, tokens and raw error traces. Known credential values are scrubbed from final strings as defense in depth.

CLI output files are created with private permissions where supported. Existing file permissions and Windows ACLs remain the operator's responsibility. Source reports contain paths and line numbers; treat them as sensitive. Retention/deletion policy and an external encrypted artifact store are not implemented yet.
