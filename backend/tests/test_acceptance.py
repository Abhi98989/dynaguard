"""Acceptance checks use real ASGI fixtures and persisted API/worker results.

Run: python -m unittest discover -s tests -v
The test database is isolated from development data.
"""
import asyncio
from datetime import timedelta
import hashlib
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app import api, worker
from app.models import Base, Evidence, Finding, ScanRun, TestExecution, now
from app.scope import ScopedClient, Incomplete
from app.security import redact, attempts
from app.verification import verify, OWN, OTHER

PASSWORD = 'synthetic-password-must-not-appear'
TOKEN = 'synthetic-token-must-not-appear'
TARGET = 'http://127.0.0.1:8101'
SNAPSHOT = {'target': TARGET, 'credential_reference': 'fixture/alice', 'timeout_seconds': 5, 'request_limit': 8}


async def progress(_):
    pass


def response_handler(mode='fixed'):
    def handler(request):
        if request.url.path == '/login':
            return httpx.Response(200, json={'user_id': 'alice', 'access_token': TOKEN})
        if request.url.path.endswith('record-a'):
            return httpx.Response(200, json=OWN)
        if mode == 'vulnerable':
            return httpx.Response(200, json=OTHER)
        return httpx.Response(403, json={'error': 'forbidden'})
    return handler


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'FIXTURE_PASSWORD': PASSWORD, 'TARGETS_JSON': json.dumps({TARGET: ['127.0.0.1']})})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def run_test(self, handler, **changes):
        return asyncio.run(verify({**SNAPSHOT, **changes}, progress, transport=httpx.MockTransport(handler)))

    def test_vulnerable_fixture_has_baseline_and_protected_record_proof(self):
        outcome, _, evidence = self.run_test(response_handler('vulnerable'))
        self.assertEqual(outcome, 'failed')
        self.assertTrue(evidence['proof']['authorized_baseline'])
        self.assertTrue(evidence['proof']['protected_record_returned'])
        self.assertEqual(evidence['request_count'], 3)
        self.assertNotIn(PASSWORD, json.dumps(evidence))
        self.assertNotIn(TOKEN, json.dumps(evidence))

    def test_fixed_fixture_denies_and_rechecks_legitimate_access(self):
        outcome, _, evidence = self.run_test(response_handler())
        self.assertEqual(outcome, 'passed')
        self.assertTrue(evidence['proof']['authorized_recheck'])
        self.assertEqual(evidence['request_count'], 4)

    def test_http_200_without_protected_record_is_inconclusive(self):
        base = response_handler()
        def handler(request):
            return httpx.Response(200, text='<html>Login required</html>') if request.url.path.endswith('record-b') else base(request)
        outcome, _, _ = self.run_test(handler)
        self.assertEqual(outcome, 'incomplete')

    def test_protected_record_in_error_response_is_still_a_bypass(self):
        base = response_handler()
        def handler(request):
            return httpx.Response(403, json=OTHER) if request.url.path.endswith('record-b') else base(request)
        self.assertEqual(self.run_test(handler)[0], 'failed')

    def test_failed_login_is_incomplete(self):
        self.assertEqual(self.run_test(lambda _: httpx.Response(401, json={'error': 'invalid_credentials'}))[0], 'incomplete')

    def test_unavailable_target_is_incomplete(self):
        def handler(request):
            raise httpx.ConnectError('internal diagnostic with ' + PASSWORD)
        outcome, actual, evidence = self.run_test(handler)
        self.assertEqual(outcome, 'incomplete')
        self.assertNotIn(PASSWORD, actual + json.dumps(evidence))

    def test_failed_baseline_is_incomplete_not_confirmed(self):
        self.assertEqual(self.run_test(lambda req: response_handler()(req) if req.url.path == '/login' else httpx.Response(200, json=OTHER))[0], 'incomplete')

    def test_expired_authentication_after_denial_is_incomplete(self):
        count = 0
        def handler(request):
            nonlocal count
            count += 1
            return httpx.Response(401, json={'error': 'unauthenticated'}) if count == 4 else response_handler()(request)
        self.assertEqual(self.run_test(handler)[0], 'incomplete')

    def test_request_limit_never_becomes_pass(self):
        outcome, _, evidence = self.run_test(response_handler(), request_limit=2)
        self.assertEqual(outcome, 'incomplete')
        self.assertEqual(evidence['request_count'], 2)

    def test_cross_origin_redirect_blocked_before_following(self):
        requests = []
        def handler(request):
            requests.append(str(request.url))
            return httpx.Response(302, headers={'Location': 'http://127.0.0.1:8999/records/record-b'}) if request.url.path.endswith('record-b') else response_handler()(request)
        outcome, actual, _ = self.run_test(handler)
        self.assertEqual(outcome, 'incomplete')
        self.assertIn('Scope blocked', actual)
        self.assertEqual(len(requests), 3)
        self.assertFalse(any('8999' in url for url in requests))

    def test_same_origin_redirect_still_requires_designated_record(self):
        base = response_handler()
        def handler(request):
            return httpx.Response(302, headers={'Location': '/records/record-a'}) if request.url.path.endswith('record-b') else base(request)
        self.assertEqual(self.run_test(handler)[0], 'incomplete')

    def test_out_of_scope_target_blocked_without_network_request(self):
        requests = []
        result = self.run_test(lambda req: requests.append(req), target='http://example.invalid:8101')
        self.assertEqual(result[0], 'incomplete')
        self.assertEqual(requests, [])

    def test_dns_rebinding_blocked(self):
        with patch('app.scope.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('169.254.169.254', 8101))]):
            outcome, actual, evidence = self.run_test(response_handler())
        self.assertEqual(outcome, 'incomplete')
        self.assertIn('Scope blocked', actual)
        self.assertEqual(evidence['request_count'], 0)

    def test_deadline_and_oversized_body_are_incomplete(self):
        self.assertEqual(self.run_test(response_handler(), timeout_seconds=0)[0], 'incomplete')
        self.assertEqual(self.run_test(lambda _: httpx.Response(200, content=b'a' * 17000))[0], 'incomplete')

    def test_redaction_covers_nested_keys_and_echoed_credentials(self):
        value = {'Authorization': 'Bearer secret', 'nested': [{'password': PASSWORD, 'error': f'echo {PASSWORD} / {TOKEN}'}]}
        sanitized = json.dumps(redact(value, [PASSWORD, TOKEN]))
        self.assertNotIn(PASSWORD, sanitized)
        self.assertNotIn(TOKEN, sanitized)
        self.assertNotIn('Bearer secret', sanitized)


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine('sqlite:///' + (Path(self.temp.name) / 'test.db').as_posix(), connect_args={'check_same_thread': False})
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(self.engine, expire_on_commit=False)
        salt = b'0123456789abcdef'
        digest = hashlib.scrypt(PASSWORD.encode(), salt=salt, n=16384, r=8, p=1).hex()
        self.env = patch.dict(os.environ, {'ADMIN_PASSWORD_HASH': salt.hex() + ':' + digest, 'SESSION_SECRET': 'session-key-for-tests-only-' * 3, 'FIXTURE_PASSWORD': PASSWORD, 'TARGETS_JSON': json.dumps({TARGET: ['127.0.0.1'], 'http://127.0.0.1:8102': ['127.0.0.1']})})
        self.env.start()
        self.api_patch = patch.object(api, 'Session', self.session)
        self.worker_patch = patch.object(worker, 'Session', self.session)
        self.api_patch.start()
        self.worker_patch.start()
        attempts.clear()
        self.client = TestClient(api.app, headers={'X-DynaGuard-Client': 'dashboard'})
        self.assertEqual(self.client.post('/auth/login', json={'username': 'admin', 'password': PASSWORD}).status_code, 200)

    def tearDown(self):
        self.client.close()
        self.api_patch.stop()
        self.worker_patch.stop()
        self.env.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def project(self):
        response = self.client.post('/projects', json={'name': 'Synthetic pilot'})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def policy(self, project, target=TARGET):
        response = self.client.post(f'/projects/{project}/environments', json={'name': 'Lab', 'target': target, 'build_id': 'fixture-v1'})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['policy']['id']

    def run_scan(self, project, policy, mode='vulnerable', retest=None):
        response = self.client.post(f'/projects/{project}/scan-runs', json={'policy_id': policy, 'retest_of': retest})
        self.assertEqual(response.status_code, 201, response.text)
        run = response.json()
        job = worker.claim()
        self.assertEqual(job[0], run['id'])
        # Exercise the actual FastAPI fixture, not only mocked HTTP responses.
        with patch.dict(os.environ, {'FIXTURE_MODE': mode}):
            import fixture.main
            fixture_app = importlib.reload(fixture.main)
            asyncio.run(worker.execute(*job, transport=httpx.ASGITransport(app=fixture_app.app)))
        return self.client.get('/scan-runs/' + run['id']).json()

    def test_complete_vulnerable_to_fixed_retest_flow_with_saved_evidence(self):
        project = self.project()
        vulnerable = self.policy(project)
        fixed = self.policy(project, 'http://127.0.0.1:8102')
        first = self.run_scan(project, vulnerable)
        self.assertEqual(first['execution']['outcome'], 'failed')
        self.assertEqual(first['finding']['verification'], 'confirmed_bypass')
        evidence = first['evidence']
        self.assertEqual(evidence['sha256'], hashlib.sha256(json.dumps(evidence['content'], sort_keys=True, separators=(',', ':')).encode()).hexdigest())
        retest = self.run_scan(project, fixed, 'fixed', first['finding']['id'])
        self.assertEqual(retest['execution']['outcome'], 'passed')
        self.assertIsNone(retest['finding'])
        detail = self.client.get('/findings/' + first['finding']['id']).json()
        self.assertEqual(detail['finding']['lifecycle'], 'verified_fixed')
        self.assertEqual(len(detail['retests']), 1)
        report = self.client.get('/scan-runs/' + first['run']['id'] + '/report').text
        self.assertNotIn(PASSWORD, report)
        from fixture.main import TOKENS
        for token in TOKENS.values():
            self.assertNotIn(token, report)
        with self.session() as session:
            self.assertEqual(len(list(session.scalars(select(Evidence)))), 2)

    def test_admin_authentication_and_csrf_required(self):
        anonymous = TestClient(api.app)
        self.assertEqual(anonymous.get('/projects').status_code, 401)
        self.assertEqual(anonymous.post('/projects', json={'name': 'x'}).status_code, 403)
        self.assertEqual(self.client.post('/projects', json={'name': 'x'}, headers={'Sec-Fetch-Site': 'cross-site'}).status_code, 403)
        self.assertEqual(self.client.post('/auth/login', json={'username': 'admin', 'password': 'wrong'}).status_code, 401)
        cookie = self.client.cookies.get('dynaguard_session')
        self.assertTrue(cookie)
        self.client.cookies.clear()
        self.client.cookies.set('dynaguard_session', cookie + 'tampered')
        self.assertEqual(self.client.get('/projects').status_code, 401)

    def test_disallowed_configuration_and_cross_project_policy_rejected(self):
        project = self.project()
        self.assertEqual(self.client.post(f'/projects/{project}/environments', json={'name': 'bad', 'target': 'http://example.com', 'build_id': 'x'}).status_code, 422)
        policy = self.policy(project)
        other = self.project()
        self.assertEqual(self.client.post(f'/projects/{other}/scan-runs', json={'policy_id': policy}).status_code, 404)

    def test_queued_cancel_prevents_claim(self):
        project = self.project()
        policy = self.policy(project)
        run = self.client.post(f'/projects/{project}/scan-runs', json={'policy_id': policy}).json()
        self.assertEqual(self.client.post('/scan-runs/' + run['id'] + '/cancel').json()['status'], 'cancelled')
        self.assertIsNone(worker.claim())

    def test_running_cancel_interrupts_pending_http_request(self):
        project = self.project()
        policy = self.policy(project)
        run = self.client.post(f'/projects/{project}/scan-runs', json={'policy_id': policy}).json()
        job = worker.claim()
        calls = []
        closed = []
        async def slow_handler(request):
            calls.append(request.url.path)
            try:
                await asyncio.sleep(20)
                return httpx.Response(200, json={})
            finally:
                closed.append(True)
        async def exercise():
            task = asyncio.create_task(worker.execute(*job, transport=httpx.MockTransport(slow_handler)))
            await asyncio.sleep(0.2)
            self.client.post('/scan-runs/' + run['id'] + '/cancel')
            await asyncio.wait_for(task, timeout=2)
        asyncio.run(exercise())
        result = self.client.get('/scan-runs/' + run['id']).json()
        self.assertEqual(result['run']['status'], 'cancelled')
        self.assertEqual(result['execution']['outcome'], 'cancelled')
        self.assertTrue(closed)
        self.assertEqual(len(calls), 1)

    def test_abandoned_worker_lease_is_incomplete(self):
        project = self.project()
        policy = self.policy(project)
        run = self.client.post(f'/projects/{project}/scan-runs', json={'policy_id': policy}).json()
        worker.claim()
        with self.session() as session, session.begin():
            session.get(ScanRun, run['id']).lease_until = now() - timedelta(seconds=1)
        worker.reap()
        result = self.client.get('/scan-runs/' + run['id']).json()
        self.assertEqual(result['run']['status'], 'incomplete')
        self.assertEqual(result['execution']['outcome'], 'incomplete')


if __name__ == '__main__':
    unittest.main()
