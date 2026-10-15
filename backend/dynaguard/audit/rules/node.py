"""Audit rules tailored for Node.js, Express, and NestJS services."""
import re
from .base import RegexRule

NODE_RULES = [
    RegexRule(
        rule_id='node.cors-wildcard-credentials',
        layer='config',
        title='CORS configuration allows wildcard or dynamic origin with credentials',
        severity='high',
        confidence='high',
        pattern=re.compile(r'cors\(\s*\{[^\}]*?origin\s*:\s*(?:true|["\']\*["\'])[^\}]*?credentials\s*:\s*true'),
        file_patterns=['.js', '.ts', '.mjs'],
        recommendation='Specify exact allowed origins when credentials: true is enabled to prevent cross-origin data theft.',
        cwe='CWE-942',
        owasp='A05:2021-Security Misconfiguration',
        stacks={'node', 'node_backend'}
    ),
    RegexRule(
        rule_id='node.jwt-decode-without-verify',
        layer='function',
        title='JWT payload decoded without signature verification (jwt.decode)',
        severity='critical',
        confidence='high',
        pattern=re.compile(r'\bjwt\.decode\s*\('),
        file_patterns=['.js', '.ts'],
        recommendation='Always use jwt.verify() with explicit secret/key and algorithm whitelist instead of jwt.decode().',
        cwe='CWE-347',
        owasp='A07:2021-Identification and Authentication Failures',
        stacks={'node', 'node_backend'}
    ),
    RegexRule(
        rule_id='node.template-literal-sqli',
        layer='database',
        title='Potential SQL injection via JavaScript template literal interpolation',
        severity='critical',
        confidence='medium',
        pattern=re.compile(r'(?:db|pool|client|sequelize|prisma)\.query\s*\(\s*`[^`]*?\$\{'),
        file_patterns=['.js', '.ts'],
        recommendation='Use parameterized query bindings or tagged templates provided by your database driver.',
        cwe='CWE-89',
        owasp='A03:2021-Injection',
        stacks={'node', 'node_backend'}
    ),
    RegexRule(
        rule_id='node.eval-dynamic-execution',
        layer='code',
        title='Dangerous dynamic JavaScript code execution (eval or new Function)',
        severity='critical',
        confidence='high',
        pattern=re.compile(r'\beval\s*\(|\bnew\s+Function\s*\('),
        file_patterns=['.js', '.ts', '.mjs'],
        recommendation='Remove eval() and new Function() calls; use standard parsing and logic branching.',
        cwe='CWE-95',
        owasp='A03:2021-Injection',
        stacks={'node', 'node_backend'}
    ),
    RegexRule(
        rule_id='node.body-parser-unbounded',
        layer='function',
        title='Missing body parser payload size limit',
        severity='low',
        confidence='medium',
        pattern=re.compile(r'express\.json\(\s*\)|bodyParser\.json\(\s*\)'),
        file_patterns=['.js', '.ts'],
        recommendation='Define a safe limit in express.json({ limit: "1mb" }) to defend against resource exhaustion / DoS.',
        cwe='CWE-770',
        owasp='A05:2021-Security Misconfiguration',
        stacks={'node', 'node_backend'}
    )
]
