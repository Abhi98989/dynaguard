"""Real-process acceptance run; uses a disposable database and loopback fixtures.

Run with the project virtualenv: python scripts/smoke.py
Add --serve to keep the temporary demo alive for browser verification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from processes import launch_options, stop_owned

ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_ready(url, process):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('A smoke-test service exited during startup')
        try:
            if httpx.get(url, timeout=1, trust_env=False).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError('Smoke-test service readiness timed out')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true', help='Keep disposable demo and dashboard alive until Ctrl+C')
    parser.add_argument('--port', type=int, default=3001, help='Dashboard port for the disposable preview')
    args = parser.parse_args()
    children = []
    logs = []
    with tempfile.TemporaryDirectory(prefix='dynaguard-smoke-') as temp:
        temp = Path(temp)
        env = dict(os.environ)
        # This password is a public synthetic test credential, used only in this disposable demo.
        admin_password = 'synthetic-password-must-not-appear'
        fixture_password = secrets.token_urlsafe(32)
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(admin_password.encode(), salt=salt, n=16384, r=8, p=1).hex()
        ports = list({free_port() for _ in range(8)})[:4]
        if len(ports) != 4:
            raise RuntimeError('Could not reserve distinct test ports')
        targets = [f'http://127.0.0.1:{port}' for port in ports]
        api_port = free_port()
        api_url = f'http://127.0.0.1:{api_port}'
        env.update(DATABASE_URL='sqlite:///' + (temp / 'smoke.db').as_posix(), ADMIN_PASSWORD_HASH=salt.hex() + ':' + digest, SESSION_SECRET=secrets.token_hex(32), FIXTURE_PASSWORD=fixture_password, TARGETS_JSON=json.dumps({target: ['127.0.0.1'] for target in targets}), API_BASE_URL=api_url, NEXT_TELEMETRY_DISABLED='1')

        def launch(name, command, process_env, cwd=ROOT / 'backend'):
            log = (temp / f'{name}.log').open('w+', encoding='utf-8')
            logs.append(log)
            process = subprocess.Popen(command, cwd=cwd, env=process_env, stdout=log, stderr=subprocess.STDOUT, **launch_options())
            children.append(process)
            return process

        try:
            subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT / 'backend', env=env, check=True, capture_output=True)
            subprocess.run([sys.executable, '-m', 'alembic', 'check'], cwd=ROOT / 'backend', env=env, check=True, capture_output=True)
            for index, mode in enumerate(['vulnerable', 'fixed', 'fixed']):
                fixture_env = {k: v for k, v in env.items() if k not in {'ADMIN_PASSWORD_HASH', 'SESSION_SECRET', 'DATABASE_URL'}}
                fixture_env['FIXTURE_MODE'] = mode
                if index == 2:
                    fixture_env['FIXTURE_PASSWORD'] = secrets.token_urlsafe(32)
                process = launch(f'fixture-{index}', [sys.executable, '-m', 'uvicorn', 'fixture.main:app', '--host', '127.0.0.1', '--port', str(ports[index]), '--no-access-log'], fixture_env)
                wait_ready(targets[index] + '/health', process)
            control_env = {k: v for k, v in env.items() if k != 'FIXTURE_PASSWORD'}
            api_process = launch('api', [sys.executable, '-m', 'uvicorn', 'app.api:app', '--host', '127.0.0.1', '--port', str(api_port), '--no-access-log'], control_env)
            wait_ready(api_url + '/health', api_process)
            worker_env = {k: v for k, v in env.items() if k not in {'ADMIN_PASSWORD_HASH', 'SESSION_SECRET'}}
            launch('worker', [sys.executable, '-m', 'app.worker'], worker_env)
            with httpx.Client(base_url=api_url, headers={'X-DynaGuard-Client': 'dashboard'}, trust_env=False, timeout=5) as client:
                assert client.get('/projects').status_code == 401
                response = client.post('/auth/login', json={'username': 'admin', 'password': admin_password})
                response.raise_for_status()
                project = client.post('/projects', json={'name': 'DynaGuard acceptance lab'}).json()['id']
                findings = []
                for index, (target, expected) in enumerate(zip(targets, ['failed', 'passed', 'incomplete', 'incomplete'])):
                    label = ['Vulnerable fixture', 'Fixed fixture', 'Invalid login fixture', 'Unavailable fixture'][index]
                    policy = client.post(f'/projects/{project}/environments', json={'name': label, 'target': target, 'build_id': ['fixture-vulnerable-v1', 'fixture-fixed-v1', 'fixture-bad-login-v1', 'fixture-unavailable-v1'][index]}).json()['policy']['id']
                    body = {'policy_id': policy}
                    if index == 1:
                        body['retest_of'] = findings[0]
                    run = client.post(f'/projects/{project}/scan-runs', json=body).json()['id']
                    deadline = time.monotonic() + 20
                    while True:
                        result = client.get(f'/scan-runs/{run}').json()
                        if result['run']['status'] in {'completed', 'incomplete', 'cancelled'}:
                            break
                        if time.monotonic() > deadline:
                            raise RuntimeError('Run did not terminate')
                        time.sleep(0.1)
                    assert result['execution']['outcome'] == expected, result['execution']['actual']
                    assert result['evidence'], 'Every executed run needs stored evidence'
                    report = client.get(f'/scan-runs/{run}/report').text
                    assert fixture_password not in report and admin_password not in report
                    if result['finding']:
                        findings.append(result['finding']['id'])
                    print(f'{label}: {expected}; evidence persisted; credentials absent from report')
                detail = client.get('/findings/' + findings[0]).json()
                assert detail['finding']['lifecycle'] == 'verified_fixed'
                assert client.post(f'/projects/{project}/environments', json={'name': 'blocked', 'target': 'http://example.invalid', 'build_id': 'none'}).status_code == 422
                print('Original finding: verified_fixed. Out-of-scope target configuration: blocked.')
            for log in logs:
                log.flush()
                log.seek(0)
                content = log.read()
                assert fixture_password not in content and admin_password not in content, 'Credential appeared in service logs'
            print('Real-process smoke verification passed; no credentials in service logs.')
            if args.serve:
                dashboard_env = {k: v for k, v in env.items() if k not in {'ADMIN_PASSWORD_HASH', 'SESSION_SECRET', 'FIXTURE_PASSWORD', 'DATABASE_URL'}}
                process = launch('dashboard', ['node', 'node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', str(args.port)], dashboard_env, ROOT / 'dashboard')
                wait_ready(f'http://127.0.0.1:{args.port}', process)
                print(f'Disposable preview: http://127.0.0.1:{args.port} (admin uses the synthetic test credential in scripts/smoke.py). Ctrl+C stops it.', flush=True)
                while all(child.poll() is None for child in children):
                    time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            for process in children:
                stop_owned(process)
            for log in logs:
                log.close()


if __name__ == '__main__':
    main()
