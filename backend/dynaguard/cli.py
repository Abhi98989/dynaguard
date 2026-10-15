"""CLI adapter for DynaGuard local verification, audits, doctor, and uploads."""
import argparse
import asyncio
import html
import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from .config import ProjectConfig
from .engine import verify, contract_hash, seal_report
from .source import scan_source
from .audit import run_audit
from .audit.plugins import get_all_plugins


def write_report(result, destination):
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')


def render_html_report(data: dict) -> str:
    mode = data.get('mode', 'audit')
    project = html.escape(str(data.get('project', 'DynaGuard Scan')))
    status = html.escape(str(data.get('status', 'unknown')))
    created_at = html.escape(str(data.get('created_at', '')))
    summary = data.get('summary', {})
    findings = data.get('findings', [])
    coverage = data.get('coverage', [])
    limitations = data.get('limitations', [])

    crit = summary.get('critical', 0)
    high = summary.get('high', 0)
    med = summary.get('medium', 0)
    low = summary.get('low', 0)
    info = summary.get('info', 0)

    rows = []
    for f in findings:
        sev = html.escape(str(f.get('severity', 'medium')))
        layer = html.escape(str(f.get('layer', 'code')))
        title = html.escape(str(f.get('title', '')))
        path = html.escape(str(f.get('path', 'n/a')))
        line = str(f.get('line', ''))
        rec = html.escape(str(f.get('recommendation', '')))
        loc = f"{path}:{line}" if line else path
        rows.append(f"""
        <tr>
          <td><span class="badge {sev}">{sev.upper()}</span></td>
          <td>{layer}</td>
          <td><strong>{title}</strong><br><small style="color:#666">{rec}</small></td>
          <td><code>{loc}</code></td>
        </tr>
        """)

    cov_rows = []
    if isinstance(coverage, list):
        for c in coverage:
            check = html.escape(str(c.get('check', '')))
            st = html.escape(str(c.get('status', '')))
            reason = html.escape(str(c.get('reason', '')))
            cov_rows.append(f"""
            <tr>
              <td><strong>{check}</strong></td>
              <td><span class="badge {st}">{st.upper()}</span></td>
              <td>{reason}</td>
            </tr>
            """)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DynaGuard {mode.capitalize()} Report · {project}</title>
<style>
  :root {{ font-family: system-ui, -apple-system, sans-serif; color: #1e293b; background: #f8fafc; padding: 20px; }}
  body {{ max-width: 1000px; margin: auto; background: white; padding: 32px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); }}
  h1 {{ margin: 0 0 6px 0; font-size: 26px; }}
  .muted {{ color: #64748b; font-size: 14px; margin-bottom: 24px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 14px; margin: 20px 0; }}
  .card {{ padding: 16px; border-radius: 8px; text-align: center; border: 1px solid #e2e8f0; }}
  .card .num {{ font-size: 28px; font-weight: bold; margin-bottom: 4px; }}
  .badge {{ display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }}
  .critical {{ background: #fef2f2; color: #991b1b; }}
  .high {{ background: #fff1f2; color: #be123c; }}
  .medium {{ background: #fffbeb; color: #b45309; }}
  .low {{ background: #f0fdf4; color: #15803d; }}
  .info, .checked {{ background: #eff6ff; color: #1d4ed8; }}
  .not_checked {{ background: #f1f5f9; color: #475569; }}
  .error {{ background: #fef2f2; color: #b91c1c; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }}
  th {{ background: #f8fafc; font-weight: 600; color: #475569; }}
  code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 12px; }}
</style>
</head>
<body>
  <h1>DynaGuard {mode.capitalize()} Report · {project}</h1>
  <div class="muted">Generated at {created_at} · Status: <span class="badge {status}">{status}</span></div>

  <div class="cards">
    <div class="card"><div class="num" style="color:#991b1b">{crit}</div>Critical</div>
    <div class="card"><div class="num" style="color:#be123c">{high}</div>High</div>
    <div class="card"><div class="num" style="color:#b45309">{med}</div>Medium</div>
    <div class="card"><div class="num" style="color:#15803d">{low}</div>Low / Info</div>
  </div>

  <h2>Findings ({len(findings)})</h2>
  <table>
    <thead><tr><th>Severity</th><th>Layer</th><th>Issue & Recommendation</th><th>Location</th></tr></thead>
    <tbody>
      {''.join(rows) if rows else '<tr><td colspan="4" style="text-align:center;padding:24px;color:#64748b">No findings recorded in this scan.</td></tr>'}
    </tbody>
  </table>

  <h2>Coverage Matrix</h2>
  <table>
    <thead><tr><th>Check</th><th>Status</th><th>Coverage Details</th></tr></thead>
    <tbody>
      {''.join(cov_rows) if cov_rows else '<tr><td colspan="3">No coverage entries recorded.</td></tr>'}
    </tbody>
  </table>

  <footer style="margin-top:32px; font-size:12px; color:#94a3b8">
    DynaGuard Shared Engine · Untested components are not certified secure.
  </footer>
</body>
</html>"""


def run_doctor():
    print("DynaGuard Scanner Plugins Doctor:")
    print("---------------------------------")
    plugins = get_all_plugins()
    for p in plugins:
        avail = p.is_available()
        path = shutil.which(p.name) or "NOT FOUND"
        status = "[INSTALLED]" if avail else "[MISSING]  "
        print(f" {status} {p.name:<14} -> {path}")
    print("\nBuilt-in Rule Packs:")
    print(" [READY]      Laravel / PHP")
    print(" [READY]      Node.js / Express / NestJS")
    print(" [READY]      Next.js / React")
    print(" [READY]      Python / Django / FastAPI")
    print(" [READY]      Flutter / Dart / Android")
    print(" [READY]      Database / SQL / Firebase")
    print(" [READY]      System Design & Monorepo Architecture")


def upload_report(report_path: str, server_url: str, token_env: str):
    token = os.environ.get(token_env, '')
    if not token:
        raise ValueError(f"Environment variable '{token_env}' is missing or empty.")

    p = Path(report_path)
    if not p.is_file():
        raise FileNotFoundError(f"Report file '{report_path}' not found.")

    payload_data = p.read_bytes()
    endpoint = server_url.rstrip('/') + '/api/ingest/audit-reports'

    req = Request(
        endpoint,
        data=payload_data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
            'X-DynaGuard-Client': 'dashboard',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 DynaGuard/2.0'
        },
        method='POST'
    )

    try:
        with urlopen(req, timeout=30) as response:
            resp_body = response.read().decode('utf-8')
            print(f"Report successfully uploaded to DynaGuard server.")
            print(f"Response: {resp_body}")
    except HTTPError as e:
        err = e.read().decode('utf-8')
        raise RuntimeError(f"Upload failed with HTTP {e.code}: {err}") from None
    except URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}") from None


def parser():
    root = argparse.ArgumentParser(prog='dynaguard', description='DynaGuard full-project audit and authorization verification')
    commands = root.add_subparsers(dest='command', required=True)

    # doctor
    commands.add_parser('doctor', help='Check status of installed security scanner plugins')

    # audit
    audit_cmd = commands.add_parser('audit', help='Perform comprehensive code, dependency, database, and design audit')
    audit_cmd.add_argument('--path', default='.', help='Project directory to scan (default: current directory)')
    audit_cmd.add_argument('--output', default='dynaguard-audit-report.json', help='Destination JSON report path')
    audit_cmd.add_argument('--html', default=None, help='Optional destination HTML report path')
    audit_cmd.add_argument('--offline', action='store_true', help='Skip external network lookups for dependency checks')
    audit_cmd.add_argument('--builtin-only', action='store_true', help='Run only built-in rules without invoking external plugins')
    audit_cmd.add_argument('--baseline', default=None, help='Previous report JSON to calculate new vs fixed findings')
    audit_cmd.add_argument('--suppression', default=None, help='Custom suppression JSON file (default: .dynaguard-ignore.json)')
    audit_cmd.add_argument('--fail-on', choices=['critical', 'high', 'medium', 'low'], default=None, help='Exit with error code if findings meet or exceed this severity')

    # upload
    upload_cmd = commands.add_parser('upload', help='Upload an audit report to your DynaGuard control plane')
    upload_cmd.add_argument('--report', required=True, help='Path to audit JSON report to upload')
    upload_cmd.add_argument('--server', default='https://dynaguard.dynamatrixsolution.live', help='DynaGuard dashboard server URL')
    upload_cmd.add_argument('--token-env', default='DYNAGUARD_UPLOAD_TOKEN', help='Environment variable containing the project upload token')

    # legacy scan
    source = commands.add_parser('scan', help='Scan local source using built-in heuristics')
    source.add_argument('kind', choices=['source'])
    source.add_argument('--path', default='.')
    source.add_argument('--output', default='dynaguard-source-report.json')

    # init, verify, discover, retest, report
    init = commands.add_parser('init', help='Write a data-only starter configuration')
    init.add_argument('--output', default='dynaguard.json')

    for name in ('verify', 'discover'):
        sub = commands.add_parser(name)
        sub.add_argument('--config', default='dynaguard.json')
        sub.add_argument('--output', default=f'dynaguard-{name}-report.json')

    retest = commands.add_parser('retest', help='Repeat one test from a previous verification report')
    retest.add_argument('--config', default='dynaguard.json')
    retest.add_argument('--report', required=True)
    retest.add_argument('--test-id', required=True)
    retest.add_argument('--output', default='dynaguard-retest-report.json')

    report_p = commands.add_parser('report', help='Render an existing JSON report as HTML')
    report_p.add_argument('--input', required=True)
    report_p.add_argument('--output', default='dynaguard-report.html')

    # qa planning and execution
    qa = commands.add_parser('qa', help='QA skill catalog, risk-based planning, and executable pre-release testing')
    qa_actions = qa.add_subparsers(dest='qa_action', required=True)

    qa_catalog = qa_actions.add_parser('catalog', help='Export catalog of 43 QA skill contracts')
    qa_catalog.add_argument('--output', default='dynaguard-qa-catalog.json')

    qa_plan = qa_actions.add_parser('plan', help='Generate risk-based QA plan from a QA profile')
    qa_plan.add_argument('--profile', required=True, help='Path to QA profile JSON')
    qa_plan.add_argument('--output', default='dynaguard-qa-plan.json')

    qa_run = qa_actions.add_parser('run', help='Execute QA test suite (API functional & browser workflows)')
    qa_run.add_argument('--suite', required=True, help='Path to QA test suite JSON')
    qa_run.add_argument('--profile', default=None, help='Optional QA profile JSON')
    qa_run.add_argument('--output', default='dynaguard-qa-results.json')
    qa_run.add_argument('--html', default=None, help='Optional HTML report path')

    qa_retest = qa_actions.add_parser('retest', help='Retest previous QA run against fixed build')
    qa_retest.add_argument('--suite', required=True, help='Path to QA test suite JSON')
    qa_retest.add_argument('--report', required=True, help='Path to previous failing QA report JSON')
    qa_retest.add_argument('--output', default='dynaguard-qa-retest.json')
    qa_retest.add_argument('--html', default=None, help='Optional HTML report path')

    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == 'doctor':
            run_doctor()
            return 0

        if args.command == 'qa':
            from .qa import catalog, QAProfile, build_plan
            if args.qa_action == 'catalog':
                Path(args.output).write_text(json.dumps(catalog(), indent=2) + '\n', encoding='utf-8')
                print(f"QA catalog (43 skills) exported to {args.output}")
                return 0

            if args.qa_action == 'plan':
                profile = QAProfile.model_validate_json(Path(args.profile).read_text(encoding='utf-8'))
                plan = build_plan(profile)
                write_report(plan, args.output)
                print(f"QA plan created: {args.output} (does not execute test adapters)")
                return 0

            if args.qa_action in ('run', 'retest'):
                from .qa_runner import QATestSuite, execute_qa_suite
                suite = QATestSuite.model_validate_json(Path(args.suite).read_text(encoding='utf-8'))
                profile = None
                if getattr(args, 'profile', None):
                    profile = QAProfile.model_validate_json(Path(args.profile).read_text(encoding='utf-8'))

                prev_report = None
                if args.qa_action == 'retest':
                    prev_report = json.loads(Path(args.report).read_text(encoding='utf-8'))

                result = execute_qa_suite(suite, profile, prev_report)
                write_report(result, args.output)
                if args.html:
                    rendered = render_html_report(result)
                    Path(args.html).write_text(rendered, encoding='utf-8')

                cov = result['coverage']
                gate = result['release_gate']
                print(f"QA {args.qa_action}: status={result['status']}; planned={cov['planned']}, passed={cov['passed']}, failed={cov['failed']}, blocked={cov['blocked']}; release={gate['decision']}")
                if result['findings']:
                    print(f"Defects found ({len(result['findings'])}):")
                    for fd in result['findings']:
                        print(f"  - [{fd['severity'].upper()}] {fd['title']}")
                return 1 if gate['decision'] == 'rejected' else 0

        if args.command == 'upload':
            upload_report(args.report, args.server, args.token_env)
            return 0

        if args.command == 'audit':
            result = run_audit(
                root=args.path,
                offline=args.offline,
                builtin_only=args.builtin_only,
                baseline_path=args.baseline,
                suppression_path=args.suppression
            )
            write_report(result, args.output)
            if args.html:
                rendered = render_html_report(result)
                Path(args.html).write_text(rendered, encoding='utf-8')

            print(f"audit: {result['status']}; findings={len(result['findings'])}; report={args.output}")
            print(f"Summary: {json.dumps(result['summary'])}")
            if args.baseline:
                print(f"Diff: {json.dumps(result['diff'])}")

            if args.fail_on:
                severities = ['low', 'medium', 'high', 'critical']
                thresh_idx = severities.index(args.fail_on)
                for f in result['findings']:
                    f_sev = f.get('severity', 'low')
                    if f_sev in severities and severities.index(f_sev) >= thresh_idx:
                        return 1
            return 0

        if args.command == 'init':
            from .starter import starter
            with open(args.output, 'x', encoding='utf-8') as f:
                json.dump(starter(), f, indent=2)
                f.write('\n')
            print('Configuration created. Review target scope and synthetic assertions before running.')
            return 0

        if args.command == 'report':
            result = json.loads(Path(args.input).read_text(encoding='utf-8'))
            rendered = render_html_report(result)
            Path(args.output).write_text(rendered, encoding='utf-8')
            print(f"Rendered HTML report saved to {args.output}")
            return 0

        if args.command == 'scan':
            result = scan_source(args.path)
            write_report(result, args.output)
            print(f"{result['mode']}: {result['status']}; findings={len(result['findings'])}; report={args.output}")
            return 0

        config = ProjectConfig.model_validate_json(Path(args.config).read_text(encoding='utf-8'))
        if args.command == 'retest':
            previous = json.loads(Path(args.report).read_text(encoding='utf-8'))
            if previous.get('mode') != 'verify' or previous.get('project') != config.project or previous.get('target') != config.target.origin:
                raise ValueError('Retest requires the same project and target as the original verification report')
            if args.test_id not in {e['test_id'] for e in previous.get('executions', [])}:
                raise ValueError('Test absent from original report')
            config.tests = [t for t in config.tests if t.id == args.test_id]
            if not config.tests:
                raise ValueError('Test absent from current configuration')
            original = next(e for e in previous['executions'] if e['test_id'] == args.test_id)
            digest = contract_hash(config, config.tests[0])
            if digest != original.get('contract_sha256'):
                raise ValueError('Test contract changed; run a new scan instead of claiming a retest')

        if args.command == 'discover':
            from .discovery import discover
            result = asyncio.run(discover(config))
        else:
            result = asyncio.run(verify(config))

        if args.command == 'retest':
            result['retest_of'] = previous['run_id']
            seal_report(result)

        write_report(result, args.output)
        print(f"{result['mode']}: {result['status']}; findings={len(result['findings'])}; report={args.output}")
        print(json.dumps(result['coverage']))
        return 2 if result['status'] != 'completed' else (1 if result['findings'] else 0)

    except KeyboardInterrupt:
        print('Cancelled.')
        return 130
    except Exception as e:
        print(f'Error: {str(e)}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
