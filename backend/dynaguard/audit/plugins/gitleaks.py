"""Adapter for Gitleaks secrets scanner."""
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple
from .base import PluginAdapter
from ..finding import AuditFinding, CoverageItem, generate_finding_id


class GitleaksPlugin(PluginAdapter):
    name = 'gitleaks'
    layer = 'secret'

    def run(self, root: Path, offline: bool = False) -> Tuple[List[AuditFinding], CoverageItem]:
        if not self.is_available():
            return [], CoverageItem(
                check='gitleaks',
                layer='secret',
                tool='gitleaks',
                status='not_checked',
                reason='gitleaks binary not installed or not in PATH'
            )

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Execute gitleaks with redaction; no shell, safe timeout
            cmd = [
                'gitleaks',
                'detect',
                '--source', str(root),
                '--report-format', 'json',
                '--report-path', str(tmp_path),
                '--redact',
                '--no-banner'
            ]
            # Gitleaks returns 0 (no leaks) or 1 (leaks found)
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            
            findings: List[AuditFinding] = []
            if tmp_path.exists() and tmp_path.stat().st_size > 0:
                raw_data = json.loads(tmp_path.read_text(encoding='utf-8', errors='ignore'))
                if isinstance(raw_data, list):
                    for item in raw_data[:500]:
                        rule_id = item.get('RuleID', 'gitleaks.secret')
                        file_path = item.get('File', '')
                        start_line = item.get('StartLine', 1)
                        description = item.get('Description', 'Hardcoded secret detected')
                        finding_id = generate_finding_id(f'gitleaks.{rule_id}', file_path, start_line, 'gitleaks')
                        findings.append(AuditFinding(
                            id=finding_id,
                            rule_id=f'gitleaks.{rule_id}',
                            tool='gitleaks',
                            layer='secret',
                            title=f'Secret detected by Gitleaks: {description}',
                            severity='high',
                            confidence='high',
                            verification='suspected',
                            path=file_path,
                            line=start_line,
                            cwe='CWE-798',
                            owasp='A07:2021-Identification and Authentication Failures',
                            recommendation='Rotate this secret immediately and ensure git history is sanitized using git-filter-repo.',
                            evidence='Gitleaks rule match; secret value has been redacted.'
                        ))

            return findings, CoverageItem(
                check='gitleaks',
                layer='secret',
                tool='gitleaks',
                status='checked',
                reason='Successfully scanned commit history and repository files for secrets.',
                items_count=len(findings)
            )
        except Exception as e:
            return [], CoverageItem(
                check='gitleaks',
                layer='secret',
                tool='gitleaks',
                status='error',
                reason=f'Scan execution failed or timed out: {str(e)}'
            )
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
