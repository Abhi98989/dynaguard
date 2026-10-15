"""Audit rules tailored for database migrations, schemas, and cloud rules."""
import re
from .base import RegexRule

DATABASE_RULES = [
    RegexRule(
        rule_id='database.grant-all-or-superuser',
        layer='database',
        title='Database script creates superuser or grants unrestricted privileges',
        severity='high',
        confidence='high',
        pattern=re.compile(r'(?i)\b(?:GRANT\s+ALL\s+PRIVILEGES|CREATE\s+ROLE\s+.*?\bSUPERUSER\b|ALTER\s+USER\s+.*?\bSUPERUSER\b)'),
        file_patterns=['.sql'],
        recommendation='Principle of least privilege: assign application users only SELECT, INSERT, UPDATE, DELETE permissions on specific tables.',
        cwe='CWE-250',
        owasp='A01:2021-Broken Access Control',
        stacks={'database'}
    ),
    RegexRule(
        rule_id='database.unbound-port-publish',
        layer='config',
        title='Database service port published to public 0.0.0.0 network in compose file',
        severity='high',
        confidence='medium',
        pattern=re.compile(r'["\'](?:5432:5432|3306:3306|27017:27017|6379:6379)["\']'),
        file_patterns=['compose.yml', 'compose.yaml', 'docker-compose.yml', 'docker-compose.yaml'],
        recommendation='Bind database ports to localhost (e.g., "127.0.0.1:5432:5432") or keep them internal to the Docker network.',
        cwe='CWE-668',
        owasp='A05:2021-Security Misconfiguration',
        stacks={'docker', 'database'}
    ),
    RegexRule(
        rule_id='firebase.open-read-write-rule',
        layer='database',
        title='Firebase / Firestore rule allows unauthenticated public read or write',
        severity='critical',
        confidence='high',
        pattern=re.compile(r'allow\s+(?:read|write|read,\s*write)\s*:\s*if\s+true\b'),
        file_patterns=['firestore.rules', 'storage.rules'],
        recommendation='Enforce authenticated user authorization checks in security rules (e.g., request.auth != null && ...).',
        cwe='CWE-284',
        owasp='A01:2021-Broken Access Control',
        stacks={'firebase'}
    )
]
