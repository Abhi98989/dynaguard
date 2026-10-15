"""Adapter for Semgrep static code analysis."""
import json
import subprocess
from pathlib import Path
from typing import List, Tuple
from .base import PluginAdapter
from ..finding import AuditFinding, CoverageItem, generate_finding_id


class SemgrepPlugin(PluginAdapter):
    name = 'semgrep'
    layer = 'code'

    def run(self, root: Path, offline: bool = False) -> Tuple[List[AuditFinding], CoverageItem]:
        if not self.is_available():
            return [], CoverageItem(
                check='semgrep',
                layer='code',
                tool='semgrep',
                status='not_checked',
                reason='semgrep binary not installed or not in PATH'
            )

        try:
            config_arg = ['--config', 'auto'] if not offline else ['--config', 'p/default']
            cmd = ['semgrep', 'scan', *config_arg, '--json', '--metrics=off', '--quiet', str(root)]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=300)
            
            findings: List[AuditFinding] = []
            if proc.stdout:
                try:
                    data = json.loads(proc.stdout)
                    results = data.get('results', [])
                    for res in results[:500]:
                        check_id = res.get('check_id', 'semgrep.rule')
                        path = res.get('path', '')
                        try:
                            rel_path = str(Path(path).relative_to(root))
                        except Exception:
                            rel_path = path

                        start = res.get('start', {}).get('line', 1)
                        extra = res.get('extra', {})
                        message = extra.get('message', 'Potential issue found by Semgrep')
                        severity_raw = extra.get('severity', 'WARNING').upper()
                        severity_map = {'ERROR': 'high', 'WARNING': 'medium', 'INFO': 'low'}
                        severity = severity_map.get(severity_raw, 'medium')
                        
                        metadata = extra.get('metadata', {})
                        cwe = metadata.get('cwe', [None])[0] if isinstance(metadata.get('cwe'), list) else metadata.get('cwe')
                        owasp = metadata.get('owasp', [None])[0] if isinstance(metadata.get('owasp'), list) else metadata.get('owasp')

                        findings.append(AuditFinding(
                            id=generate_finding_id(f'semgrep.{check_id}', rel_path, start, 'semgrep'),
                            rule_id=f'semgrep.{check_id}',
                            tool='semgrep',
                            layer='code',
                            title=f'Semgrep finding: {check_id.split(".")[-1]}',
                            severity=severity,
                            confidence='high',
                            verification='suspected',
                            path=rel_path,
                            line=start,
                            cwe=str(cwe) if cwe else None,
                            owasp=str(owasp) if owasp else None,
                            recommendation=message,
                            evidence='Semgrep AST rule match.'
                        ))
                except json.JSONDecodeError:
                    pass

            return findings, CoverageItem(
                check='semgrep',
                layer='code',
                tool='semgrep',
                status='checked',
                reason='Scanned source code using Semgrep AST dataflow analysis.',
                items_count=len(findings)
            )
        except Exception as e:
            return [], CoverageItem(
                check='semgrep',
                layer='code',
                tool='semgrep',
                status='error',
                reason=f'semgrep execution error: {str(e)}'
            )
