import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
import httpx
from dynaguard.config import ProjectConfig, Target, Limits
from dynaguard.engine import verify
from dynaguard.network import ScopedHTTP, Budget, Incomplete
from dynaguard.source import scan_source
from dynaguard.cli import main

SECRET = 'synthetic-test-password-only'


def contract(origin='http://127.0.0.1:8910'):
    return ProjectConfig.model_validate({
        'project': 'Different application', 'build_id': 'v1',
        'target': {'origin': origin, 'pinned_ips': ['127.0.0.1'], 'allow_private': True, 'allowed_paths': ['/session', '/api/me', '/api/tickets/7', '/app', '/asset.js']},
        'identities': {
            'owner': {'kind': 'json_login', 'login_path': '/session', 'username': 'manager', 'username_field': 'email', 'password_field': 'passcode', 'password_env': 'DYNAGUARD_TEST_PASSWORD', 'token_field': 'session.token', 'auth_check': {'path': '/api/me', 'expected': {'name': 'manager'}}},
            'member': {'kind': 'json_login', 'login_path': '/session', 'username': 'member', 'username_field': 'email', 'password_field': 'passcode', 'password_env': 'DYNAGUARD_TEST_PASSWORD', 'token_field': 'session.token', 'auth_check': {'path': '/api/me', 'expected': {'name': 'member'}}},
            'anonymous': {'kind': 'anonymous'}},
        'tests': [{'id': 'tickets.owner', 'title': 'Ticket owner boundary', 'authorized_identity': 'owner', 'probe_identity': 'member', 'resource': {'path': '/api/tickets/7', 'expected': {'ticket.id': 'synthetic-7'}}}, {'id': 'tickets.anonymous', 'title': 'Anonymous ticket boundary', 'authorized_identity': 'owner', 'probe_identity': 'anonymous', 'resource': {'path': '/api/tickets/7', 'expected': {'ticket.id': 'synthetic-7'}}}],
        'discovery_paths': ['/app'], 'discovery_identity': 'member'})


def handler(vulnerable=True, ambiguous=False):
    def serve(request):
        if request.url.path == '/session':
            data = json.loads(request.content)
            if data.get('passcode') != SECRET:
                return httpx.Response(401)
            return httpx.Response(200, json={'session': {'token': data['email'] + '-secret'}})
        user = request.headers.get('authorization', '').removeprefix('Bearer ').removesuffix('-secret')
        if request.url.path == '/api/me':
            return httpx.Response(200, json={'name': user})
        if request.url.path == '/api/tickets/7':
            if user == 'manager' or (vulnerable and user == 'member'):
                return httpx.Response(200, json={'ticket': {'id': 'synthetic-7'}, 'password': SECRET})
            if ambiguous:
                return httpx.Response(200, text='<html>Login</html>')
            return httpx.Response(403)
        return httpx.Response(404)
    return serve


class SharedEngineTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'DYNAGUARD_TEST_PASSWORD': SECRET})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def run_config(self, config=None, serve=None):
        return asyncio.run(verify(config or contract(), transport=httpx.MockTransport(serve or handler())))

    def test_multiple_tests_and_non_fixture_contract(self):
        result = self.run_config()
        self.assertEqual([e['outcome'] for e in result['executions']], ['failed', 'passed'])
        self.assertEqual(len(result['findings']), 1)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn('manager-secret', json.dumps(result))

    def test_fixed_and_ambiguous(self):
        self.assertEqual(self.run_config(serve=handler(False))['coverage']['passed'], 2)
        result = self.run_config(serve=handler(False, True))
        self.assertEqual(result['status'], 'incomplete')
        self.assertFalse(result['findings'])

    def test_failed_login_and_budget_are_incomplete(self):
        self.assertEqual(self.run_config(serve=lambda r: httpx.Response(401))['status'], 'incomplete')
        config = contract(); config.limits.requests = 1
        self.assertEqual(self.run_config(config)['status'], 'incomplete')

    def test_missing_identity_health_check_rejected(self):
        value = contract().model_dump(); value['identities']['owner']['auth_check'] = None
        with self.assertRaises(ValueError): ProjectConfig.model_validate(value)

    def test_inline_password_rejected(self):
        value = contract().model_dump(); value['identities']['owner']['password'] = SECRET
        with self.assertRaises(ValueError): ProjectConfig.model_validate(value)

    def test_cross_origin_redirect_never_followed(self):
        calls = []
        def redirect(request):
            calls.append(str(request.url)); return httpx.Response(302, headers={'location': 'http://unrelated.invalid/api/me'})
        result = self.run_config(serve=redirect)
        self.assertEqual(result['status'], 'incomplete')
        self.assertFalse(any('unrelated' in u for u in calls))

    def test_dns_rebinding_blocked(self):
        with patch('dynaguard.network.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('169.254.169.254', 80))]):
            result = self.run_config()
        self.assertEqual(result['coverage']['requests'], 0)
        self.assertEqual(result['status'], 'incomplete')

    def test_https_preserves_hostname_verification_extension(self):
        config = contract('https://app.example.test')
        seen = []
        async def exercise():
            client = ScopedHTTP(config.target, Budget(config.limits), httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(200)))
            try: await client.request('GET', '/api/me')
            finally: await client.close()
        with patch('dynaguard.network.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]): asyncio.run(exercise())
        self.assertEqual(seen[0].extensions['sni_hostname'], 'app.example.test')
        self.assertEqual(seen[0].headers['host'], 'app.example.test')
        self.assertEqual(seen[0].url.host, '127.0.0.1')

    def test_cookie_login_uses_original_hostname(self):
        config = contract('https://app.example.test')
        for identity in config.identities.values():
            if identity.kind == 'json_login': identity.session = 'cookie'
        def cookie_server(request):
            if request.url.path == '/session':
                user = json.loads(request.content)['email']
                return httpx.Response(200, json={}, headers={'set-cookie': f'session={user}-secret; Domain=app.example.test; Path=/; Secure; HttpOnly'})
            user = request.headers.get('cookie', '').removeprefix('session=').removesuffix('-secret')
            if request.url.path == '/api/me': return httpx.Response(200, json={'name': user})
            if user in ('manager', 'member'): return httpx.Response(200, json={'ticket': {'id': 'synthetic-7'}})
            return httpx.Response(403)
        with patch('dynaguard.network.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            result = self.run_config(config, cookie_server)
        self.assertEqual(result['coverage']['failed'], 1)
        self.assertEqual(result['coverage']['passed'], 1)
        self.assertNotIn('manager-secret', json.dumps(result))

    def test_private_scope_requires_opt_in(self):
        with self.assertRaises(ValueError): Target(origin='http://127.0.0.1', pinned_ips=['127.0.0.1'], allowed_paths=['/'])

    def test_source_masks_literals_and_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('password = "' + SECRET + '"\nverify=False')
            (root / 'linked.py').symlink_to(root / 'app.py')
            report = scan_source(root)
            self.assertEqual(len(report['findings']), 2)
            self.assertEqual(report['coverage']['files_scanned'], 1)
            self.assertNotIn(SECRET, json.dumps(report))

    def test_empty_source_is_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(scan_source(directory)['status'], 'incomplete')

    def test_html_report_escapes_untrusted_content(self):
        with tempfile.TemporaryDirectory() as directory:
            source, dest = Path(directory)/'r.json', Path(directory)/'r.html'
            source.write_text(json.dumps({'title': '<script>alert(1)</script>'}))
            self.assertEqual(main(['report', '--input', str(source), '--output', str(dest)]), 0)
            self.assertNotIn('<script>', dest.read_text())


class LiveApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vulnerable = True
        class App(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self): self.respond()
            def do_GET(self): self.respond()
            def respond(self):
                if self.path == '/app':
                    body = b'<html><body><div id="result"></div><script src="/asset.js"></script></body></html>'
                    self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers(); self.wfile.write(body); return
                if self.path == '/asset.js':
                    body = b'fetch("/api/me").then(r=>r.json()).then(v=>document.querySelector("#result").textContent=v.name)'
                    self.send_response(200); self.send_header('Content-Type', 'application/javascript'); self.end_headers(); self.wfile.write(body); return
                request = httpx.Request(self.command, 'http://127.0.0.1' + self.path, headers=dict(self.headers), content=self.rfile.read(int(self.headers.get('Content-Length', '0'))))
                response = handler(cls.vulnerable)(request)
                self.send_response(response.status_code)
                self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(response.content)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), App)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.origin = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def test_cli_real_http_and_retest(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'DYNAGUARD_TEST_PASSWORD': SECRET}):
            config = Path(d)/'config.json'; report = Path(d)/'report.json'; retest = Path(d)/'retest.json'
            config.write_text(contract(self.origin).model_dump_json())
            type(self).vulnerable = True
            self.assertEqual(main(['verify', '--config', str(config), '--output', str(report)]), 1)
            type(self).vulnerable = False
            self.assertEqual(main(['retest', '--config', str(config), '--report', str(report), '--test-id', 'tickets.owner', '--output', str(retest)]), 0)
            self.assertEqual(json.loads(retest.read_text())['coverage']['passed'], 1)
            changed = contract(self.origin); changed.tests[0].title = 'Different test'
            config.write_text(changed.model_dump_json())
            self.assertEqual(main(['retest', '--config', str(config), '--report', str(report), '--test-id', 'tickets.owner', '--output', str(retest)]), 2)

    @unittest.skipUnless(os.environ.get('DYNAGUARD_BROWSER_TEST') == '1', 'Set DYNAGUARD_BROWSER_TEST=1 after installing Chromium')
    def test_browser_renders_js_and_captures_authenticated_api(self):
        from dynaguard.discovery import discover
        with patch.dict(os.environ, {'DYNAGUARD_TEST_PASSWORD': SECRET}):
            report = asyncio.run(discover(contract(self.origin)))
        self.assertEqual(report['status'], 'completed', report)
        self.assertTrue(any(r['path'] == '/api/me' and r.get('status') == 200 for r in report['requests']))
        self.assertEqual(report['coverage']['rendered_pages'], 1)
