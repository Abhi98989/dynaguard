"""Common rule pack applicable to all codebases regardless of framework."""
import re
from .base import RegexRule

COMMON_RULES = [
    RegexRule(
        rule_id='secret.private-key',
        layer='secret',
        title='Private key material exposed in source',
        severity='critical',
        confidence='high',
        pattern=re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
        recommendation='Remove private key material from repository immediately, assess exposure history, and rotate affected keys.',
        cwe='CWE-798',
        owasp='A07:2021-Identification and Authentication Failures'
    ),
    RegexRule(
        rule_id='secret.hardcoded-credential',
        layer='secret',
        title='Possible hardcoded credential or API token',
        severity='high',
        confidence='medium',
        pattern=re.compile(r'''(?i)\b(?:password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|secret[_-]?key)\b["']?\s*[:=]\s*["']([^"'\n]{8,})["']'''),
        recommendation='Store credentials in secure environment variables or vault references; rotate any exposed values.',
        cwe='CWE-798',
        owasp='A07:2021-Identification and Authentication Failures'
    ),
    RegexRule(
        rule_id='tls.disabled',
        layer='config',
        title='TLS certificate verification is disabled',
        severity='high',
        confidence='high',
        pattern=re.compile(r'\bverify\s*=\s*False\b|\brejectUnauthorized\s*:\s*false\b|\bInsecureSkipVerify\s*:\s*true\b'),
        recommendation='Always enable TLS certificate and hostname verification in production communication.',
        cwe='CWE-295',
        owasp='A02:2021-Cryptographic Failures'
    ),
    RegexRule(
        rule_id='process.shell-execution',
        layer='code',
        title='Dangerous shell command invocation detected',
        severity='high',
        confidence='medium',
        pattern=re.compile(r'\bshell\s*=\s*True\b|\bchild_process\.exec\s*\(|\bos\.system\s*\('),
        recommendation='Avoid invoking subshells with string interpolation; pass argument arrays to prevent command injection.',
        cwe='CWE-78',
        owasp='A03:2021-Injection'
    ),
    RegexRule(
        rule_id='code.todo-security-marker',
        layer='design',
        title='Unresolved security/auth TODO or FIXME marker in code',
        severity='low',
        confidence='medium',
        pattern=re.compile(r'(?i)\b(?:TODO|FIXME|HACK|XXX)\b.*?\b(?:security|auth|bypass|vulnerability|token|leak|hack)\b'),
        recommendation='Review and resolve outstanding security markers before promoting code to production.',
        cwe='CWE-546',
        owasp='A05:2021-Security Misconfiguration'
    )
]
