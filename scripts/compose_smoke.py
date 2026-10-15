"""Build and verify the actual PostgreSQL/Compose stack, then remove only its test volume."""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import threading
import time

import httpx
from processes import launch_options, stop_owned
from compose_checks import deployment_checks

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'dynaguard-acceptance-' + secrets.token_hex(4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--minimum-free-gib', type=float, default=5, help='Initial free-space requirement; lower only when images/layers are already cached')
    parser.add_argument('--skip-build', action='store_true', help='Verify existing application images without rebuilding')
    args = parser.parse_args()
    if args.minimum_free_gib < 2:
        parser.error('At least 2 GiB must be required')
    if shutil.disk_usage(ROOT).free < args.minimum_free_gib * 1024 ** 3:
        raise SystemExit(f'Compose verification needs at least {args.minimum_free_gib:g} GiB free. Free space before retrying.')
    password = secrets.token_urlsafe(24)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
    values = {'POSTGRES_PASSWORD': secrets.token_hex(24), 'ADMIN_PASSWORD_HASH': salt.hex() + ':' + digest, 'SESSION_SECRET': secrets.token_hex(32), 'FIXTURE_PASSWORD': secrets.token_hex(24)}
    with tempfile.TemporaryDirectory(prefix='dynaguard-compose-') as temp:
        env_file = Path(temp) / '.env'
        env_file.write_text(''.join(f'{key}={value}\n' for key, value in values.items()), encoding='utf-8')
        compose = ['docker', 'compose', '-p', PROJECT, '--env-file', str(env_file)]

        def checked(command):
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', **launch_options())
            def relay():
                for line in process.stdout:
                    # Docker emits UTF-8 even on Windows consoles using a legacy code page.
                    safe = line.encode('ascii', errors='backslashreplace').decode('ascii')
                    print(safe, end='', flush=True)
            output = threading.Thread(target=relay, daemon=True)
            output.start()
            try:
                while process.poll() is None:
                    if shutil.disk_usage(ROOT).free < 512 * 1024 ** 2:
                        raise RuntimeError('Verification stopped because free disk space dropped below 512 MiB')
                    time.sleep(0.5)
                if process.returncode:
                    raise subprocess.CalledProcessError(process.returncode, command)
            finally:
                stop_owned(process)
                output.join(timeout=5)
                process.stdout.close()

        try:
            # Bound peak build disk usage; the shared backend image is built once.
            if not args.skip_build:
                checked([*compose, 'build', 'api'])
                checked([*compose, 'build', 'dashboard'])
            checked([*compose, 'up', '--no-build', '-d', '--wait', '--wait-timeout', '120'])
            subprocess.run([*compose, 'exec', '-T', 'api', 'alembic', 'check'], cwd=ROOT, check=True)
            with httpx.Client(base_url='http://127.0.0.1:3000/api', headers={'X-DynaGuard-Client': 'dashboard'}, trust_env=False, timeout=10) as client:
                assert client.get('/projects').status_code == 401
                client.post('/auth/login', json={'username': 'admin', 'password': password}).raise_for_status()
                project = client.post('/projects', json={'name': 'Compose acceptance project'}).json()['id']
                finding = None
                policies = {}
                for mode in ['vulnerable', 'fixed']:
                    policy = client.post(f'/projects/{project}/environments', json={'name': mode, 'target': f'http://fixture-{mode}:8000', 'build_id': f'fixture-{mode}-v1'}).json()['policy']['id']
                    policies[mode] = policy
                    run = client.post(f'/projects/{project}/scan-runs', json={'policy_id': policy, 'retest_of': finding}).json()['id']
                    deadline = time.monotonic() + 30
                    while True:
                        result = client.get('/scan-runs/' + run).json()
                        if result['run']['status'] in {'completed', 'incomplete', 'cancelled'}:
                            break
                        if time.monotonic() >= deadline:
                            raise RuntimeError('Compose run timed out')
                        time.sleep(0.2)
                    assert result['execution']['outcome'] == ('failed' if mode == 'vulnerable' else 'passed'), result['execution']['actual']
                    report = client.get('/scan-runs/' + run + '/report').text
                    assert values['FIXTURE_PASSWORD'] not in report and password not in report
                    if mode == 'vulnerable':
                        finding = result['finding']['id']
                    print(f'Compose / PostgreSQL / dashboard proxy: {mode} verified')
                assert client.get('/findings/' + finding).json()['finding']['lifecycle'] == 'verified_fixed'
                deployment_checks(client, compose, ROOT, project, policies, finding, values, env_file, checked)
            logs = subprocess.run([*compose, 'logs', '--no-color'], cwd=ROOT, capture_output=True, text=True, check=True).stdout
            assert password not in logs and values['FIXTURE_PASSWORD'] not in logs
            print('Compose acceptance passed; PostgreSQL migrations match models; credentials absent from logs.')
        finally:
            # This isolated project and volume are created solely by this acceptance script.
            subprocess.run([*compose, 'down', '--volumes', '--remove-orphans'], cwd=ROOT, check=False)


if __name__ == '__main__':
    main()
