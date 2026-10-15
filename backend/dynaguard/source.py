"""Small transparent heuristic pack. Does not execute project code or install packages."""
import hashlib
import os
from pathlib import Path
import re
from .engine import report_base

EXCLUDED = {'.git', '.venv', 'venv', 'node_modules', '.next', 'build', 'dist', '__pycache__', '.dart_tool', '.idea'}
TEXT_SUFFIXES = {'.py', '.js', '.jsx', '.ts', '.tsx', '.dart', '.java', '.kt', '.swift', '.json', '.yaml', '.yml', '.toml', '.ini', '.conf', '.sql', '.html', '.xml', '.properties', '.sh', '.env'}
RULES = [
    ('secret.private-key', 'Private key material', 'high', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'), 'Remove private key material from source, assess exposure, and rotate affected credentials.'),
    ('secret.assignment', 'Possible hardcoded credential', 'high', re.compile(r'''(?i)\b(?:password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token)\b["']?\s*[:=]\s*["']([^"'\n]{8,})["']'''), 'Check whether this literal is a real private credential. If so, rotate it and use a secret reference.'),
    ('tls.disabled', 'TLS verification may be disabled', 'medium', re.compile(r'\bverify\s*=\s*False\b|\brejectUnauthorized\s*:\s*false\b'), 'Enable certificate and hostname verification; validate context before changing test-only code.'),
    ('frontend.html', 'Potential unsafe HTML rendering', 'medium', re.compile(r'\bdangerouslySetInnerHTML\b|\.innerHTML\s*='), 'Trace the rendered input and ensure untrusted HTML is sanitized before rendering.'),
    ('database.public-rule', 'Potential public database access rule', 'high', re.compile(r'allow\s+(?:read|write|read,\s*write)\s*:\s*if\s+true\b'), 'Review the database rules and require the intended identity and ownership checks.'),
    ('database.superuser', 'Database superuser declaration requires review', 'medium', re.compile(r'(?i)\b(?:CREATE|ALTER)\s+(?:ROLE|USER)\b[^;\n]*\bSUPERUSER\b'), 'Application roles should have only required privileges; distinguish provisioning scripts from runtime roles.'),
    ('process.shell', 'Shell execution requires review', 'medium', re.compile(r'\bshell\s*=\s*True\b'), 'Review input flow and prefer argument arrays without a shell.'),
]


def scan_source(root, max_files=10000):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('Source path must be an existing directory')
    result = report_base('source', root.name)
    scanned = skipped = errors = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        skipped += sum(d in EXCLUDED or (Path(directory) / d).is_symlink() for d in dirs)
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if path.is_symlink() or (path.suffix not in TEXT_SUFFIXES and name != 'Dockerfile' and not name.startswith('.env')):
                skipped += 1
                continue
            if scanned >= max_files:
                result['status'] = 'incomplete'
                errors += 1
                break
            try:
                if path.stat().st_size > 1048576:
                    skipped += 1
                    continue
                content = path.read_text(encoding='utf-8')
            except (OSError, UnicodeError):
                errors += 1
                continue
            scanned += 1
            relative = path.relative_to(root).as_posix()
            result['findings'].extend(inspect_text(content, relative))
            if len(result['findings']) >= 1000:
                result['findings'] = result['findings'][:1000]
                result['status'] = 'incomplete'
                errors += 1
                break
        if scanned >= max_files or len(result['findings']) >= 1000:
            break
    if errors or not scanned:
        result['status'] = 'incomplete'
    result['coverage'] = {'files_scanned': scanned, 'entries_skipped': skipped, 'read_errors_or_limits': errors, 'rules': len(RULES)}
    result['limitations'] = ['Heuristics only; false positives and false negatives are expected.', 'No Git history, dependency advisory database, dataflow, database policy or runtime verification.', 'Symlinks, generated/vendor directories, non-text files and files over 1 MiB are excluded.']
    return result


def inspect_text(content, location):
    findings = []
    for rule_id, title, severity, pattern, recommendation in RULES:
        for match in pattern.finditer(content):
            line = content.count('\n', 0, match.start()) + 1
            findings.append({'id': hashlib.sha256(f'{rule_id}:{location}:{line}'.encode()).hexdigest(), 'rule_id': rule_id, 'title': title, 'severity': severity, 'verification': 'suspected', 'path': location, 'line': line, 'recommendation': recommendation, 'evidence': 'Pattern matched; source text and secret values intentionally omitted.'})
            if len(findings) >= 1000:
                return findings
    return findings
