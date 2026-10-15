"""Orchestrator for built-in rules, stack detection, external plugins, suppressions, and baseline diffs."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
from uuid import uuid4

from .finding import AuditFinding, CoverageItem
from .stack import detect_stacks, EXCLUDE_DIRS
from .rules import get_applicable_rules
from .rules.design import check_project_design
from .plugins import get_all_plugins

TEXT_SUFFIXES = {
    '.py', '.js', '.jsx', '.ts', '.tsx', '.dart', '.java', '.kt', '.swift',
    '.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.sql', '.html',
    '.xml', '.properties', '.sh', '.env', '.php', '.blade.php', '.rules'
}


def run_audit(
    root: Path | str,
    offline: bool = False,
    builtin_only: bool = False,
    baseline_path: Path | str | None = None,
    suppression_path: Path | str | None = None,
    max_files: int = 10000
) -> Dict[str, Any]:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValueError('Root path must be an existing directory')

    # 1. Detect Stacks
    stacks = detect_stacks(root_path)

    # 2. Prepare built-in rules
    rules = get_applicable_rules(stacks)

    findings: List[AuditFinding] = []
    coverage: List[CoverageItem] = []

    # 3. Walk project files for built-in checks
    scanned_files = 0
    skipped_files = 0
    file_errors = 0

    for directory, dirs, files in os.walk(root_path, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            file_p = Path(directory) / name
            if file_p.is_symlink() or (file_p.suffix not in TEXT_SUFFIXES and name != 'Dockerfile' and not name.startswith('.env')):
                skipped_files += 1
                continue

            if scanned_files >= max_files:
                file_errors += 1
                break

            try:
                if file_p.stat().st_size > 1048576:  # 1MB limit per file
                    skipped_files += 1
                    continue
                content = file_p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                file_errors += 1
                continue

            scanned_files += 1
            rel_path = file_p.relative_to(root_path).as_posix()

            for rule in rules:
                rule_findings = rule.scan(content, rel_path)
                findings.extend(rule_findings)

        if scanned_files >= max_files:
            break

    # Built-in project design checks
    findings.extend(check_project_design(root_path))

    coverage.append(CoverageItem(
        check='builtin-rules',
        layer='code',
        tool='builtin',
        status='checked',
        reason=f'Scanned {scanned_files} files across {len(rules)} built-in rules tailored for {list(stacks) or ["generic"]}.',
        items_count=len(findings)
    ))

    # 4. Run external plugin scanners if requested
    if not builtin_only:
        plugins = get_all_plugins()
        for plugin in plugins:
            p_findings, p_coverage = plugin.run(root_path, offline=offline)
            findings.extend(p_findings)
            coverage.append(p_coverage)

    # 5. Deduplicate findings
    seen_ids: Set[str] = set()
    unique_findings: List[AuditFinding] = []
    for f in findings:
        if f.id not in seen_ids:
            seen_ids.add(f.id)
            unique_findings.append(f)

    # 6. Apply suppressions (.dynaguard-ignore.json)
    suppressions: Set[str] = set()
    s_path = Path(suppression_path) if suppression_path else (root_path / '.dynaguard-ignore.json')
    if s_path.is_file():
        try:
            s_data = json.loads(s_path.read_text(encoding='utf-8'))
            now_iso = datetime.now(timezone.utc).isoformat()
            for item in s_data.get('ignore', []):
                fid = item.get('id')
                exp = item.get('expires_at')
                if fid and (not exp or exp > now_iso):
                    suppressions.add(fid)
        except Exception:
            pass

    active_findings = [f for f in unique_findings if f.id not in suppressions]
    suppressed_count = len(unique_findings) - len(active_findings)

    # 7. Baseline diff
    diff_stats = {'new': len(active_findings), 'unchanged': 0, 'fixed': 0}
    findings_out = []
    if baseline_path and Path(baseline_path).is_file():
        try:
            base_data = json.loads(Path(baseline_path).read_text(encoding='utf-8'))
            base_ids = {f['id'] for f in base_data.get('findings', [])}
            current_ids = {f.id for f in active_findings}
            fixed_count = len(base_ids - current_ids)
            unchanged_count = len(base_ids & current_ids)
            new_count = len(current_ids - base_ids)
            diff_stats = {'new': new_count, 'unchanged': unchanged_count, 'fixed': fixed_count}
            for f in active_findings:
                d = f.model_dump()
                d['is_new'] = f.id not in base_ids
                findings_out.append(d)
        except Exception:
            findings_out = [f.model_dump() for f in active_findings]
    else:
        for f in active_findings:
            d = f.model_dump()
            d['is_new'] = True
            findings_out.append(d)

    # 8. Summary statistics
    severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    layer_counts: Dict[str, int] = {}
    for f in active_findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
        layer_counts[f.layer] = layer_counts.get(f.layer, 0) + 1

    report = {
        'schema_version': 2,
        'mode': 'audit',
        'run_id': str(uuid4()),
        'project': root_path.name,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'status': 'completed' if file_errors == 0 else 'incomplete',
        'stacks': sorted(list(stacks)),
        'summary': severity_counts,
        'by_layer': layer_counts,
        'coverage': [c.model_dump() for c in coverage],
        'diff': diff_stats,
        'findings': findings_out,
        'suppressed': suppressed_count,
        'limitations': [
            'Static heuristic and pattern-based analysis; findings indicate suspected weaknesses requiring verification.',
            'No live database connection or exploit payload injection performed in audit mode.',
            'Files matching exclusion lists (.git, .venv, node_modules, build artifacts) or exceeding 1 MB were omitted.'
        ]
    }

    # Integrity seal
    report_copy = dict(report)
    report_copy.pop('evidence_sha256', None)
    report['evidence_sha256'] = hashlib.sha256(json.dumps(report_copy, sort_keys=True).encode()).hexdigest()

    return report
