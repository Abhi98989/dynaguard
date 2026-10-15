"""Adapter for Google OSV-Scanner dependency vulnerability checker."""
import json
import subprocess
from pathlib import Path
from typing import List, Tuple
from .base import PluginAdapter
from ..finding import AuditFinding, CoverageItem, generate_finding_id


class OsvPlugin(PluginAdapter):
    name = 'osv-scanner'
    layer = 'dependency'

    def run(self, root: Path, offline: bool = False) -> Tuple[List[AuditFinding], CoverageItem]:
        if offline:
            return [], CoverageItem(
                check='osv-scanner',
                layer='dependency',
                tool='osv-scanner',
                status='not_checked',
                reason='Skipped because --offline mode was requested'
            )

        if not self.is_available():
            return [], CoverageItem(
                check='osv-scanner',
                layer='dependency',
                tool='osv-scanner',
                status='not_checked',
                reason='osv-scanner binary not installed or not in PATH'
            )

        try:
            cmd = ['osv-scanner', '--format', 'json', '-r', str(root)]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            
            findings: List[AuditFinding] = []
            if proc.stdout:
                try:
                    data = json.loads(proc.stdout)
                    results = data.get('results', [])
                    for result in results:
                        source_path = result.get('source', {}).get('path', '')
                        try:
                            rel_source = str(Path(source_path).relative_to(root))
                        except Exception:
                            rel_source = source_path

                        packages = result.get('packages', [])
                        for pkg in packages:
                            pkg_info = pkg.get('package', {})
                            pkg_name = pkg_info.get('name', 'unknown')
                            pkg_version = pkg_info.get('version', '')
                            vulns = pkg.get('vulnerabilities', [])
                            for vuln in vulns:
                                vuln_id = vuln.get('id', 'VULN')
                                summary = vuln.get('summary', 'Known vulnerability in dependency')
                                finding_id = generate_finding_id(f'osv.{vuln_id}', rel_source, None, 'osv-scanner')
                                findings.append(AuditFinding(
                                    id=finding_id,
                                    rule_id=f'osv.{vuln_id}',
                                    tool='osv-scanner',
                                    layer='dependency',
                                    title=f'{pkg_name}@{pkg_version}: {summary}',
                                    severity='high',
                                    confidence='high',
                                    verification='suspected',
                                    path=rel_source,
                                    line=None,
                                    cwe='CWE-1395',
                                    owasp='A06:2021-Vulnerable and Outdated Components',
                                    recommendation=f'Upgrade {pkg_name} to a patched version per advisory {vuln_id}.',
                                    evidence=f'Advisory {vuln_id} affects {pkg_name} version {pkg_version}.'
                                ))
                except json.JSONDecodeError:
                    pass

            return findings, CoverageItem(
                check='osv-scanner',
                layer='dependency',
                tool='osv-scanner',
                status='checked',
                reason='Scanned dependencies against the OSV open-source vulnerability database.',
                items_count=len(findings)
            )
        except Exception as e:
            return [], CoverageItem(
                check='osv-scanner',
                layer='dependency',
                tool='osv-scanner',
                status='error',
                reason=f'osv-scanner execution error: {str(e)}'
            )
