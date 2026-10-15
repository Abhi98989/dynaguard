"""Deployment-only acceptance checks for the disposable Compose test project."""
import json
import subprocess
import time


def deployment_checks(client, compose, root, project, policies, finding, values, env_file, checked):
    def result(run_id):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            response = client.get('/scan-runs/' + run_id)
            response.raise_for_status()
            value = response.json()
            if value['run']['status'] in {'completed', 'incomplete', 'cancelled'}:
                return value
            time.sleep(0.2)
        raise RuntimeError('Deployment test run did not terminate')

    def queue():
        response = client.post(f'/projects/{project}/scan-runs', json={'policy_id': policies['fixed'], 'retest_of': finding})
        response.raise_for_status()
        return response.json()['id']

    # An allowed service that disappears must never produce a passing result.
    checked([*compose, 'stop', 'fixture-fixed'])
    unavailable = result(queue())
    assert unavailable['execution']['outcome'] == 'incomplete'
    assert unavailable['finding'] is None and unavailable['evidence'] is not None
    assert client.get('/findings/' + finding).json()['finding']['lifecycle'] == 'verified_fixed'
    print('Compose unavailable target: incomplete; prior conclusive retest retained', flush=True)

    # Give only the fixture a different synthetic password. Worker credentials stay unchanged.
    changed = {**values, 'FIXTURE_PASSWORD': values['FIXTURE_PASSWORD'] + '-invalid-login'}
    try:
        env_file.write_text(''.join(f'{key}={value}\n' for key, value in changed.items()), encoding='utf-8')
        checked([*compose, 'up', '--no-build', '--no-deps', '--force-recreate', '-d', 'fixture-fixed'])
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            health = subprocess.run([*compose, 'exec', '-T', 'fixture-fixed', 'python', '-c', "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"], cwd=root, capture_output=True)
            if health.returncode == 0:
                break
            time.sleep(0.3)
        else:
            raise RuntimeError('Invalid-login fixture did not become ready')
        failed_login = result(queue())
        assert failed_login['execution']['outcome'] == 'incomplete'
        assert failed_login['execution']['actual'] == 'Synthetic account login failed'
        assert failed_login['finding'] is None and failed_login['evidence'] is not None
        assert changed['FIXTURE_PASSWORD'] not in json.dumps(failed_login)
        print('Compose failed login: incomplete with saved masked evidence', flush=True)
    finally:
        env_file.write_text(''.join(f'{key}={value}\n' for key, value in values.items()), encoding='utf-8')
        checked([*compose, 'up', '--no-build', '--no-deps', '--force-recreate', '-d', 'fixture-fixed'])

    blocked = client.post(f'/projects/{project}/environments', json={'name': 'Outside scope', 'target': 'http://example.invalid', 'build_id': 'none'})
    assert blocked.status_code == 422

    # Hold one row lock and prove another connection claims the other job without
    # blocking or duplicating it. This exercises actual PostgreSQL SKIP LOCKED.
    checked([*compose, 'stop', 'worker'])
    first, second = queue(), queue()
    locking = f'''
from sqlalchemy import select
from app.db import Session
from app.models import ScanRun
from app.worker import claim, finish
with Session() as holding:
    locked = holding.scalar(select(ScanRun).where(ScanRun.id == {first!r}).with_for_update())
    job = claim()
    assert job is not None and job[0] == {second!r}, "Locked job was not skipped"
    holding.rollback()
job = claim()
assert job is not None and job[0] == {first!r}, "Unlocked job was not claimable"
for run_id in ({first!r}, {second!r}):
    finish(run_id, 'incomplete', 'Claim-lock acceptance check only; permission test not executed', {{'steps': []}})
print('PostgreSQL concurrent claims: locked row skipped; both jobs claimed once')
'''
    checked([*compose, 'exec', '-T', 'api', 'python', '-c', locking])
    assert result(first)['execution']['outcome'] == 'incomplete'
    assert result(second)['execution']['outcome'] == 'incomplete'

    queued = queue()
    cancel = client.post('/scan-runs/' + queued + '/cancel')
    cancel.raise_for_status()
    assert cancel.json()['status'] == 'cancelled'
    checked([*compose, 'exec', '-T', 'api', 'python', '-c', "from app.worker import claim; assert claim() is None; print('PostgreSQL queued cancellation: cancelled job is not claimable')"])

    def capture(arguments):
        return subprocess.run(arguments, cwd=root, capture_output=True, text=True, check=True).stdout.strip()

    for service in ('worker', 'fixture-vulnerable', 'fixture-fixed'):
        container = capture([*compose, 'ps', '-a', '-q', service])
        restricted = capture(['docker', 'inspect', '--format', '{{.HostConfig.ReadonlyRootfs}}|{{.Config.User}}|{{json .HostConfig.CapDrop}}|{{json .HostConfig.SecurityOpt}}|{{json .HostConfig.PortBindings}}', container]).split('|')
        assert restricted[0] == 'true' and restricted[1] == '10001'
        assert 'ALL' in json.loads(restricted[2])
        assert any(item.startswith('no-new-privileges') for item in json.loads(restricted[3]))
        assert json.loads(restricted[4]) in (None, {})
    compose_project = compose[compose.index('-p') + 1]
    for network in ('control', 'fixtures'):
        assert capture(['docker', 'network', 'inspect', compose_project + '_' + network, '--format', '{{.Internal}}']) == 'true'
    print('Worker/fixtures: non-root, read-only, capabilities dropped, no host ports; control/fixture networks internal', flush=True)
