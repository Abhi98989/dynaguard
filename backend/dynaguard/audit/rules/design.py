"""Audit rules for architectural and system design quality."""
from pathlib import Path
from typing import List
from .base import Rule
from ..finding import AuditFinding, generate_finding_id


class GodFileRule(Rule):
    def __init__(self):
        super().__init__(
            rule_id='design.god-file',
            layer='design',
            title='Excessively large source file (>1,500 lines) indicating monolithic design',
            severity='low',
            confidence='high',
            recommendation='Break down large monolithic classes and files into focused, testable modules and services.',
            cwe='CWE-1061',
            owasp='A04:2021-Insecure Design'
        )

    def scan(self, content: str, rel_path: str, context: dict | None = None) -> List[AuditFinding]:
        # Exclude generated files and migrations
        if any(skip in rel_path for skip in ('migrations/', 'schema.sql', '.min.', 'package-lock.json', 'yarn.lock')):
            return []

        lines = content.count('\n') + 1
        if lines > 1500:
            finding_id = generate_finding_id(self.id, rel_path, 1, 'builtin')
            return [AuditFinding(
                id=finding_id,
                rule_id=self.id,
                tool='builtin',
                layer=self.layer,
                title=f'{self.title} ({lines} lines)',
                severity=self.severity,
                confidence=self.confidence,
                verification='suspected',
                path=rel_path,
                line=1,
                cwe=self.cwe,
                owasp=self.owasp,
                recommendation=self.recommendation,
                evidence=f'File has {lines} lines exceeding the recommended 1,500 line threshold.'
            )]
        return []


def check_project_design(root_path: Path) -> List[AuditFinding]:
    """Project-level structural checks."""
    findings = []
    
    # 1. Check for .env file present vs .gitignore
    env_file = root_path / '.env'
    gitignore_file = root_path / '.gitignore'
    
    if env_file.is_file():
        if not gitignore_file.is_file():
            findings.append(AuditFinding(
                id=generate_finding_id('design.missing-gitignore', '.gitignore', 1, 'builtin'),
                rule_id='design.missing-gitignore',
                tool='builtin',
                layer='design',
                title='.env file present but repository lacks a .gitignore file',
                severity='high',
                confidence='high',
                verification='suspected',
                path='.gitignore',
                line=1,
                cwe='CWE-200',
                owasp='A05:2021-Security Misconfiguration',
                recommendation='Create a .gitignore file immediately and add .env to prevent committing sensitive secrets.',
                evidence='.env exists in project root but .gitignore does not.'
            ))
        else:
            gitignore_text = gitignore_file.read_text(encoding='utf-8', errors='ignore')
            if '.env' not in gitignore_text:
                findings.append(AuditFinding(
                    id=generate_finding_id('design.env-not-ignored', '.gitignore', 1, 'builtin'),
                    rule_id='design.env-not-ignored',
                    tool='builtin',
                    layer='design',
                    title='.env file is not excluded in .gitignore',
                    severity='high',
                    confidence='high',
                    verification='suspected',
                    path='.gitignore',
                    line=1,
                    cwe='CWE-200',
                    owasp='A05:2021-Security Misconfiguration',
                    recommendation='Add .env to .gitignore to ensure production passwords and keys cannot be accidentally committed.',
                    evidence='.gitignore does not mention .env'
                ))

    # 2. Check for presence of test directory
    test_dirs = ['tests', 'test', '__tests__', 'spec']
    has_tests = any((root_path / d).is_dir() for d in test_dirs)
    if not has_tests:
        findings.append(AuditFinding(
            id=generate_finding_id('design.no-automated-tests', None, None, 'builtin'),
            rule_id='design.no-automated-tests',
            tool='builtin',
            layer='design',
            title='No automated test directory (tests/ or test/) found in project',
            severity='info',
            confidence='medium',
            verification='suspected',
            path=None,
            line=None,
            cwe='CWE-1065',
            owasp='A04:2021-Insecure Design',
            recommendation='Implement automated unit and integration tests to ensure security assumptions and regressions are verified.',
            evidence='None of tests/, test/, or __tests__/ directories exist in project.'
        ))

    return findings
