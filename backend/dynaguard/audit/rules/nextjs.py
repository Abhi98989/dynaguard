"""Audit rules tailored for Next.js and React frontend applications."""
import re
from .base import RegexRule

NEXTJS_RULES = [
    RegexRule(
        rule_id='nextjs.public-secret-leak',
        layer='secret',
        title='Sensitive key or password exposed through NEXT_PUBLIC_ variable name',
        severity='critical',
        confidence='high',
        pattern=re.compile(r'(?i)\bNEXT_PUBLIC_[A-Z0-9_]*(?:SECRET|PRIVATE|PASSWORD|PASSWD|API_KEY|TOKEN|CREDENTIAL)\b'),
        file_patterns=['.env', '.env.local', '.ts', '.tsx', '.js', '.jsx'],
        recommendation='Never prefix private credentials or signing secrets with NEXT_PUBLIC_; keep server secrets private.',
        cwe='CWE-200',
        owasp='A01:2021-Broken Access Control',
        stacks={'nextjs', 'react'}
    ),
    RegexRule(
        rule_id='nextjs.dangerously-set-inner-html',
        layer='code',
        title='Potential Cross-Site Scripting (XSS) via dangerouslySetInnerHTML',
        severity='medium',
        confidence='medium',
        pattern=re.compile(r'dangerouslySetInnerHTML\s*=\s*\{\s*\{\s*__html\s*:'),
        file_patterns=['.jsx', '.tsx'],
        recommendation='Sanitize untrusted HTML inputs with DOMPurify or sanitize-html before injecting into DOM.',
        cwe='CWE-79',
        owasp='A03:2021-Injection',
        stacks={'nextjs', 'react'}
    ),
    RegexRule(
        rule_id='nextjs.unbounded-api-proxy',
        layer='function',
        title='Reverse proxy route with permissive wildcard target forwarding',
        severity='medium',
        confidence='low',
        pattern=re.compile(r'fetch\s*\(\s*[`\'"].*?\$\{path'),
        file_patterns=['route.ts', 'route.js'],
        recommendation='Validate path parameters against an allowed whitelist regex before proxying upstream.',
        cwe='CWE-918',
        owasp='A10:2021-Server-Side Request Forgery (SSRF)',
        stacks={'nextjs'}
    )
]
