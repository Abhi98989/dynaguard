# DynaGuard Audit Guide

DynaGuard v2 provides automated security and quality audits for vibe-coded and custom applications across multiple tech stacks:
- **Laravel & PHP**
- **Node.js, Express & NestJS**
- **Next.js & React**
- **Python, Django & FastAPI**
- **Flutter, Dart & Android**
- **Database schemas, migrations & Firebase rules**
- **System design & architecture patterns**

---

## 1. Quick Verification (`dynaguard doctor`)

Run `dynaguard doctor` to check the status of your built-in rule packs and optional scanner plugins:

```bash
dynaguard doctor
```

Output will show which plugins are installed (`[INSTALLED]`) vs missing (`[MISSING]`). Missing plugins will not stop scans; they are reported as `not_checked` in the coverage matrix.

---

## 2. Running an Audit

To audit any project folder:

```bash
# Basic audit using built-in rules & available plugins
dynaguard audit --path /path/to/project --output audit-report.json --html audit-report.html

# Run only built-in rules (fastest, no dependencies)
dynaguard audit --path /path/to/project --builtin-only

# Offline mode (skips external vulnerability database lookups)
dynaguard audit --path /path/to/project --offline

# Compare against a previous baseline to track new vs fixed issues
dynaguard audit --path /path/to/project --baseline last-report.json
```

---

## 3. Suppressing Accepted Findings (`.dynaguard-ignore.json`)

To suppress specific known issues, place a `.dynaguard-ignore.json` in the root of your project:

```json
{
  "ignore": [
    {
      "id": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "reason": "Test fixture containing deliberate dummy credentials",
      "expires_at": "2027-01-01T00:00:00Z"
    }
  ]
}
```

Expired suppressions automatically resurface in audit reports.

---

## 4. Uploading Reports to Dashboard

1. Open your DynaGuard dashboard at `https://dynaguard.dynamatrixsolution.live`.
2. Select your project and expand **CLI Upload Tokens & Setup Instructions**.
3. Generate an upload token and set it in your environment:

```bash
export DYNAGUARD_UPLOAD_TOKEN="dgt_your_generated_token_here"
```

4. Upload the report directly:

```bash
dynaguard upload --report audit-report.json --server https://dynaguard.dynamatrixsolution.live
```

The report will instantly appear under the **Audit Runs** section with complete metrics, coverage matrix, and filterable findings.
