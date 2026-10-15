"""Optional non-Docker smoke/demo launcher. SQLite is for local verification only."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from processes import launch_options, stop_owned

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = dict(os.environ)
    if not (ROOT / '.env').exists():
        raise SystemExit('Run python scripts/setup.py first.')
    for line in (ROOT / '.env').read_text().splitlines():
        if line and not line.startswith('#'):
            key, value = line.split('=', 1)
            env[key] = value
    env['DATABASE_URL'] = 'sqlite:///' + (ROOT / 'dynaguard.db').as_posix()
    env['TARGETS_JSON'] = '{"http://127.0.0.1:8101":["127.0.0.1"],"http://127.0.0.1:8102":["127.0.0.1"]}'
    env['API_BASE_URL'] = 'http://127.0.0.1:8000'
    env['NEXT_TELEMETRY_DISABLED'] = '1'
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT / 'backend', env=env, check=True)
    children = []
    try:
        for mode, port in [('vulnerable', '8101'), ('fixed', '8102')]:
            fixture_env = {k: v for k, v in env.items() if k not in {'ADMIN_PASSWORD_HASH', 'SESSION_SECRET', 'POSTGRES_PASSWORD', 'DATABASE_URL'}}
            children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'fixture.main:app', '--host', '127.0.0.1', '--port', port, '--no-access-log'], cwd=ROOT / 'backend', env={**fixture_env, 'FIXTURE_MODE': mode}, **launch_options()))
        control_env = {k: v for k, v in env.items() if k != 'FIXTURE_PASSWORD'}
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.api:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log'], cwd=ROOT / 'backend', env=control_env, **launch_options()))
        worker_env = {k: v for k, v in env.items() if k not in {'ADMIN_PASSWORD_HASH', 'SESSION_SECRET', 'POSTGRES_PASSWORD'}}
        children.append(subprocess.Popen([sys.executable, '-m', 'app.worker'], cwd=ROOT / 'backend', env=worker_env, **launch_options()))
        dashboard_env = {k: v for k, v in env.items() if k not in {'ADMIN_PASSWORD_HASH', 'SESSION_SECRET', 'POSTGRES_PASSWORD', 'DATABASE_URL', 'FIXTURE_PASSWORD'}}
        children.append(subprocess.Popen([shutil.which('node'), 'node_modules/next/dist/bin/next', 'dev', '--hostname', '127.0.0.1'], cwd=ROOT / 'dashboard', env=dashboard_env, **launch_options()))
        print('DynaGuard: http://127.0.0.1:3000 — Ctrl+C stops all services. Local fixtures on loopback only.')
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            stop_owned(child)


if __name__ == '__main__':
    main()
