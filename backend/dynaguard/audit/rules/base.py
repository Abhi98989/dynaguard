"""Base rule definition and pattern helpers."""
import re
from typing import List, Pattern, Set
from ..finding import AuditFinding, generate_finding_id, LayerType, SeverityType, ConfidenceType


class Rule:
    def __init__(
        self,
        rule_id: str,
        layer: LayerType,
        title: str,
        severity: SeverityType,
        confidence: ConfidenceType,
        recommendation: str,
        cwe: str | None = None,
        owasp: str | None = None,
        stacks: Set[str] | None = None,
    ):
        self.id = rule_id
        self.layer = layer
        self.title = title
        self.severity = severity
        self.confidence = confidence
        self.recommendation = recommendation
        self.cwe = cwe
        self.owasp = owasp
        self.stacks = stacks

    def scan(self, content: str, rel_path: str, context: dict | None = None) -> List[AuditFinding]:
        raise NotImplementedError


class RegexRule(Rule):
    def __init__(
        self,
        rule_id: str,
        layer: LayerType,
        title: str,
        severity: SeverityType,
        confidence: ConfidenceType,
        pattern: Pattern | str,
        recommendation: str,
        file_patterns: List[str] | None = None,
        cwe: str | None = None,
        owasp: str | None = None,
        stacks: Set[str] | None = None,
        evidence_msg: str = "Pattern matched; source text and sensitive values omitted."
    ):
        super().__init__(rule_id, layer, title, severity, confidence, recommendation, cwe, owasp, stacks)
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.file_patterns = file_patterns
        self.evidence_msg = evidence_msg

    def scan(self, content: str, rel_path: str, context: dict | None = None) -> List[AuditFinding]:
        if self.file_patterns:
            if not any(rel_path.endswith(ext) or ext in rel_path for ext in self.file_patterns):
                return []

        findings = []
        for match in self.pattern.finditer(content):
            line = content.count('\n', 0, match.start()) + 1
            finding_id = generate_finding_id(self.id, rel_path, line, 'builtin')
            findings.append(AuditFinding(
                id=finding_id,
                rule_id=self.id,
                tool='builtin',
                layer=self.layer,
                title=self.title,
                severity=self.severity,
                confidence=self.confidence,
                verification='suspected',
                path=rel_path,
                line=line,
                cwe=self.cwe,
                owasp=self.owasp,
                recommendation=self.recommendation,
                evidence=self.evidence_msg
            ))
        return findings
