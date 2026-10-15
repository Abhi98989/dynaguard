"""Audit rules tailored for Python, Django, FastAPI, and Flask services."""
import re
from .base import RegexRule

PYTHON_RULES = [
    RegexRule(
        rule_id='python.debug-mode-enabled',
        layer='config',
        title='Django or Flask debug mode enabled in production settings',
        severity='high',
        confidence='high',
        pattern=re.compile(r'^\s*DEBUG\s*=\s*True\b', re.MULTILINE),
        file_patterns=['settings.py', '.env'],
        recommendation='Ensure DEBUG is set to False in production environments to avoid leaking environment state and stack traces.',
        cwe='CWE-215',
        owasp='A05:2021-Security Misconfiguration',
        stacks={'python'}
    ),
    RegexRule(
        rule_id='python.raw-sql-formatting',
        layer='database',
        title='Potential SQL injection via Python string formatting or f-string',
        severity='critical',
        confidence='medium',
        pattern=re.compile(r'(?:cursor|session|conn)\.execute\s*\(\s*(?:f["\']|["\'].*?%s.*?["\']\s*%|["\'].*?format\()'),
        file_patterns=['.py'],
        recommendation='Pass SQL parameters as a separate tuple or mapping argument to cursor.execute(query, params).',
        cwe='CWE-89',
        owasp='A03:2021-Injection',
        stacks={'python'}
    ),
    RegexRule(
        rule_id='python.insecure-deserialization-pickle',
        layer='code',
        title='Insecure deserialization using pickle.loads on untrusted data',
        severity='critical',
        confidence='high',
        pattern=re.compile(r'\bpickle\.loads\s*\(|\b_pickle\.loads\s*\('),
        file_patterns=['.py'],
        recommendation='Never unpickle data received from untrusted sources; use JSON or signed serialization formats.',
        cwe='CWE-502',
        owasp='A08:2021-Software and Data Integrity Failures',
        stacks={'python'}
    ),
    RegexRule(
        rule_id='python.yaml-unsafe-load',
        layer='code',
        title='Unsafe YAML deserialization (yaml.load without SafeLoader)',
        severity='high',
        confidence='high',
        pattern=re.compile(r'\byaml\.load\s*\(\s*[^,\)]+\)'),
        file_patterns=['.py'],
        recommendation='Use yaml.safe_load() or specify Loader=yaml.SafeLoader to avoid arbitrary object instantiation.',
        cwe='CWE-502',
        owasp='A08:2021-Software and Data Integrity Failures',
        stacks={'python'}
    ),
    RegexRule(
        rule_id='python.django-wildcard-allowed-hosts',
        layer='config',
        title='Django ALLOWED_HOSTS configured with wildcard (*)',
        severity='medium',
        confidence='high',
        pattern=re.compile(r'ALLOWED_HOSTS\s*=\s*\[\s*["\']\*["\']\s*\]'),
        file_patterns=['settings.py'],
        recommendation='Specify the exact domain names for ALLOWED_HOSTS to prevent HTTP Host header poisoning attacks.',
        cwe='CWE-183',
        owasp='A05:2021-Security Misconfiguration',
        stacks={'python'}
    )
]
