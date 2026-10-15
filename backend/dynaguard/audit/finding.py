"""Unified finding schema, severity, and confidence levels for all audit checks."""
import hashlib
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

LayerType = Literal['code', 'function', 'database', 'design', 'dependency', 'secret', 'config']
SeverityType = Literal['info', 'low', 'medium', 'high', 'critical']
ConfidenceType = Literal['low', 'medium', 'high']
VerificationType = Literal['suspected', 'confirmed']
CoverageStatus = Literal['checked', 'not_checked', 'error']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AuditFinding(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    rule_id: str = Field(min_length=1, max_length=120)
    tool: str = Field(min_length=1, max_length=60, default='builtin')
    layer: LayerType
    title: str = Field(min_length=1, max_length=200)
    severity: SeverityType = 'medium'
    confidence: ConfidenceType = 'medium'
    verification: VerificationType = 'suspected'
    path: str | None = None
    line: int | None = None
    cwe: str | None = None
    owasp: str | None = None
    recommendation: str = Field(min_length=1)
    evidence: str = Field(min_length=1)


class CoverageItem(StrictModel):
    check: str
    layer: LayerType
    tool: str
    status: CoverageStatus
    reason: str = ''
    items_count: int = 0


def generate_finding_id(rule_id: str, path: str | None, line: int | None, tool: str = 'builtin') -> str:
    seed = f"{rule_id}:{path or ''}:{line or 0}:{tool}".encode('utf-8')
    return hashlib.sha256(seed).hexdigest()
