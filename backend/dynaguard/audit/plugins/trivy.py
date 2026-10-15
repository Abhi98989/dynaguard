"""Adapter for Aqua Security Trivy scanner."""
import json
import subprocess
from pathlib import Path
from typing import List, Tuple
from .base import PluginAdapter
from ..finding import AuditFinding, CoverageItem, generate_finding_id


class TrivyPlugin(PluginAdapter):
    name = 'trivy'
    layer = 'config'

    def run(self, root: Path, offline: bool = False) -> Tuple[List[AuditFinding], CoverageItem]:
        if not self.is_available():
            return [], CoverageItem(
                check='trivy',
                layer='config',
                tool='trivy',
                status='not_checked',
                reason='trivy binary not installed or not in PATH'
            )

        try:
            cmd = ['trivy', 'fs', '--format', 'json', '--scanners', 'misconfig,secret', '--quiet', str(root)]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            
            findings: List[AuditFinding] = []
            if proc.stdout:
                try:
                    data = json.loads(proc.stdout)
                    results = data.get('Results', [])
                    for res in results:
                        target = res.get('Target', '')
                        try:
                            rel_target = str(Path(target).relative_to(root))
                        except Exception:
                            rel_target = target

                        misconfigs = res.get('Misconfigurations', [])
                        for mis in misconfigs:
                            rule_id = mis.get('ID', 'trivy.misconfig')
                            title = mis.get('Title', 'Configuration issue')
                            msg = mis.get('Message', '')
                            sev_raw = mis.get('Severity', 'MEDIUM').lower()
                            line = mis.get('CauseMetadata', {}).get('StartLine', 1)

                            findings.append(AuditFinding(
                                id=generate_finding_id(f'trivy.{rule_id}', rel_target, line, 'trivy'),
                                rule_id=f'trivy.{rule_id}',
                                tool='trivy',
                                layer='config',
                                title=f'{title}: {msg[:100]}',
                                severity='high' if sev_raw == 'high' else ('critical' if sev_raw == 'critical' else 'medium'),
                                confidence='high',
                                verification='suspected',
                                path=rel_target,
                                line=line,
                                cwe=None,
                                owasp='A05:2021-Security Misconfiguration',
                                recommendation=mis.get('Resolution', 'Review configuration according to best practices.'),
                                evidence='Trivy misconfiguration check match.'
                            ))
                except json.JSONDecodeError:
                    pass

            return findings, CoverageItem(
                check='trivy',
                layer='config',
                tool='trivy',
                status='checked',
                reason='Scanned filesystem for configuration and infrastructure security issues.',
                items_count=len(findings)
            )
        except Exception as e:
            return [], CoverageItem(
                check='trivy',
                layer='config',
                tool='trivy',
                status='error',
                reason=f'trivy execution error: {str(e)}'
            )
