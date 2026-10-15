"""Executable authorization assertions, never inference from status code alone."""
import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
from .network import Budget, ScopedHTTP, Incomplete


def field(value, dotted):
    for key in dotted.split('.'):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def payload(response):
    try:
        return response.json()
    except ValueError:
        return None


def matches(value, expected):
    return all(type(field(value, k)) is type(v) and field(value, k) == v for k, v in expected.items())


def mask(value, secrets):
    if isinstance(value, str):
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret, '[REDACTED]')
        return value
    if isinstance(value, list):
        return [mask(v, secrets) for v in value]
    if isinstance(value, dict):
        return {k: mask(v, secrets) for k, v in value.items()}
    return value


def report_base(mode, project):
    return {'schema_version': 1, 'run_id': str(uuid4()), 'mode': mode, 'project': project,
            'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'completed',
            'executions': [], 'findings': [], 'coverage': {}, 'limitations': []}


class Session:
    def __init__(self, identity, target, budget, secrets, transport=None):
        self.identity = identity
        self.http = ScopedHTTP(target, budget, transport)
        self.secrets = secrets

    async def login(self):
        identity = self.identity
        if identity.kind == 'anonymous':
            return
        if identity.kind == 'bearer':
            token = os.environ.get(identity.token_env, '')
            if not token:
                raise Incomplete('Required credential environment variable is missing')
            self.secrets.append(token)
            self.http.headers['Authorization'] = 'Bearer ' + token
        else:
            password = os.environ.get(identity.password_env, '')
            if not password:
                raise Incomplete('Required credential environment variable is missing')
            self.secrets.append(password)
            response = await self.http.request('POST', identity.login_path, json={identity.username_field: identity.username, identity.password_field: password})
            # Include cookie values in redaction even when login fails.
            self.secrets.extend(cookie.value for cookie in self.http.cookies.jar)
            if response.status_code != 200:
                raise Incomplete('Configured JSON login failed')
            if identity.session == 'bearer':
                token = field(payload(response), identity.token_field)
                if not isinstance(token, str) or not token or len(token) > 8192:
                    raise Incomplete('Login response lacks configured token field')
                self.secrets.append(token)
                self.http.headers['Authorization'] = 'Bearer ' + token
        await self.check()

    async def check(self):
        check = self.identity.auth_check
        if self.identity.kind == 'anonymous':
            return
        response = await self.http.request('GET', check.path)
        if response.status_code != 200 or not matches(payload(response), check.expected):
            raise Incomplete('Identity health check failed; no permission conclusion possible')


def contract_hash(config, test):
    document = {'test': test.model_dump(), 'identities': {name: config.identities[name].model_dump() for name in (test.authorized_identity, test.probe_identity)}}
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()


def seal_report(result):
    result.pop('evidence_sha256', None)
    result['evidence_sha256'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


async def verify(config, progress=None, transport=None):
    result = report_base('verify', config.project)
    result['build_id'] = config.build_id
    result['target'] = config.target.origin
    result['limitations'] = ['Read authorization only; no injection, write-workflow, database or mobile exploitation.', 'Build identifiers are supplied labels; findings apply only to the tested environment.']
    budget, secrets = Budget(config.limits), []
    for test in config.tests:
        if progress:
            await progress('Testing ' + test.id)
        execution = {'test_id': test.id, 'title': test.title, 'outcome': 'incomplete', 'evidence': [], 'actual': '', 'contract_sha256': contract_hash(config, test)}
        sessions = {}
        try:
            for name in (test.authorized_identity, test.probe_identity):
                sessions[name] = Session(config.identities[name], config.target, budget, secrets, transport)
                await sessions[name].login()
            owner, probe = sessions[test.authorized_identity], sessions[test.probe_identity]
            baseline = await owner.http.request('GET', test.resource.path)
            baseline_ok = baseline.status_code == 200 and matches(payload(baseline), test.resource.expected)
            execution['evidence'].append({'step': 'authorized_baseline', 'identity': test.authorized_identity, 'status': baseline.status_code, 'assertions_matched': baseline_ok})
            if not baseline_ok:
                raise Incomplete('Authorized baseline did not match the configured synthetic resource')
            response = await probe.http.request('GET', test.resource.path)
            disclosed = matches(payload(response), test.resource.expected)
            execution['evidence'].append({'step': 'unauthorized_probe', 'identity': test.probe_identity, 'path': test.resource.path.split('?')[0], 'status': response.status_code, 'assertions_matched': disclosed, 'matched_fields': list(test.resource.expected) if disclosed else []})
            if disclosed:
                execution.update(outcome='failed', actual='The probe identity received the designated protected resource.')
                fingerprint = hashlib.sha256(f'{config.project}:{test.id}:{config.target.origin}'.encode()).hexdigest()
                result['findings'].append({'id': fingerprint, 'test_id': test.id, 'title': test.title, 'severity': test.severity, 'verification': 'confirmed_bypass', 'recommendation': test.recommendation, 'root_cause': 'Authorization failure demonstrated; source-level cause has not been established.'})
            else:
                denials = (401, 403, 404) if probe.identity.kind == 'anonymous' else (403, 404)
                if response.status_code not in denials:
                    raise Incomplete('Unexpected response; neither a bypass nor a valid denial was established')
                await probe.check()
                await owner.check()
                execution.update(outcome='passed', actual='Access denied; configured authenticated identities remain valid.')
                execution['evidence'].append({'step': 'identity_rechecks', 'passed': True})
        except Incomplete as error:
            execution['actual'] = str(error)
        finally:
            for session in sessions.values():
                await session.http.close()
        result['executions'].append(execution)
    counts = {state: sum(e['outcome'] == state for e in result['executions']) for state in ('passed', 'failed', 'incomplete')}
    result['coverage'] = {'planned': len(config.tests), **counts, 'requests': budget.count}
    if counts['incomplete'] or not config.tests:
        result['status'] = 'incomplete'
    return seal_report(mask(result, secrets))
