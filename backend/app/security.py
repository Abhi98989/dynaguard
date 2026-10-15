import hashlib
import hmac
import os
import re
import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

COOKIE = 'dynaguard_session'
attempts = defaultdict(deque)


def signer():
    key = os.environ.get('SESSION_SECRET', '')
    if len(key) < 32:
        raise RuntimeError('Configure SESSION_SECRET with at least 32 characters')
    return URLSafeTimedSerializer(key, salt='dynaguard-admin-v1')


def check_password(password):
    stored = os.environ.get('ADMIN_PASSWORD_HASH', '')
    try:
        salt, digest = stored.split(':')
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


def rate_limit(request):
    key = request.client.host if request.client else 'unknown'
    queue = attempts[key]
    cutoff = time.monotonic() - 60
    while queue and queue[0] < cutoff:
        queue.popleft()
    if len(queue) >= 10:
        raise HTTPException(429, 'Too many login attempts; wait one minute')
    queue.append(time.monotonic())


def require_admin(request: Request):
    try:
        if signer().loads(request.cookies.get(COOKIE, ''), max_age=28800) != 'administrator':
            raise BadSignature('Invalid role')
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, 'Administrator login required')


SENSITIVE = re.compile(r'password|passwd|secret|token|authorization|cookie|api.?key', re.I)


def redact(value, secrets=()):
    if isinstance(value, dict):
        return {str(k): '[REDACTED]' if SENSITIVE.search(str(k)) else redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if isinstance(value, str):
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret, '[REDACTED]')
        value = re.sub(r'(?i)bearer\s+[^\s"<>]+', 'Bearer [REDACTED]', value)
    return value
