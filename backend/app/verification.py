import os
from .models import now
from .scope import ScopedClient, Incomplete
from .security import redact

OWN = {'id': 'record-a', 'owner_id': 'alice', 'project_id': 'project-a', 'marker': 'synthetic-alice-731'}
OTHER = {'id': 'record-b', 'owner_id': 'bob', 'project_id': 'project-b', 'marker': 'synthetic-bob-942'}


def body(response):
    try:
        value = response.json()
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def matches(value, expected):
    return all(value.get(key) == wanted for key, wanted in expected.items())


async def verify(snapshot, progress, transport=None, evidence=None):
    evidence = evidence if evidence is not None else {'steps': []}
    password = os.environ.get('FIXTURE_PASSWORD', '')
    if snapshot['credential_reference'] != 'fixture/alice' or not password:
        return 'incomplete', 'Fixture credential reference unavailable', evidence
    secrets = [password]
    client = ScopedClient(snapshot['target'], snapshot['request_limit'], snapshot['timeout_seconds'], transport=transport)

    def record(name, path, response, payload):
        # Persist only known proof fields; arbitrary response text and headers are excluded.
        safe = {key: payload[key] for key in ('id', 'owner_id', 'project_id', 'marker', 'error') if key in payload and isinstance(payload[key], str)}
        evidence['steps'].append(redact({'name': name, 'recorded_at': now().isoformat(), 'request': {'path': path, 'authorization': '[REDACTED]'}, 'response': {'status': response.status_code, 'body': safe}}, secrets))

    try:
        await progress('Authenticating synthetic Alice')
        response = await client.request('POST', '/login', json={'username': 'alice', 'password': password})
        payload = body(response)
        token = payload.get('access_token')
        if isinstance(token, str):
            secrets.append(token)
        record('login', '/login', response, {})
        if response.status_code != 200 or not isinstance(token, str) or not token or len(token) > 1024 or payload.get('user_id') != 'alice':
            raise Incomplete('Synthetic account login failed')
        headers = {'Authorization': f'Bearer {token}'}
        await progress('Checking authorized baseline')
        response = await client.request('GET', '/records/record-a', headers=headers)
        payload = body(response)
        record('authorized_baseline', '/records/record-a', response, payload)
        if response.status_code != 200 or not matches(payload, OWN):
            raise Incomplete('Authorized baseline did not return the designated Alice record')
        await progress('Checking cross-owner access')
        response = await client.request('GET', '/records/record-b', headers=headers)
        payload = body(response)
        record('cross_owner_probe', '/records/record-b', response, payload)
        if matches(payload, OTHER):
            evidence['proof'] = {'authorized_baseline': True, 'protected_record_returned': True, 'fixture': 'record-b'}
            return 'failed', 'Alice received Bob’s designated protected record, including its synthetic marker.', evidence
        if response.status_code not in (403, 404) or payload.get('error') != 'forbidden':
            raise Incomplete('Ambiguous denial or expired authentication; no bypass confirmed')
        await progress('Rechecking authorized access after denial')
        response = await client.request('GET', '/records/record-a', headers=headers)
        payload = body(response)
        record('authorized_recheck', '/records/record-a', response, payload)
        if response.status_code != 200 or not matches(payload, OWN):
            raise Incomplete('Authorized recheck failed; denial may reflect authentication loss')
        evidence['proof'] = {'authorized_baseline': True, 'protected_record_returned': False, 'authorized_recheck': True}
        return 'passed', 'Bob’s record was denied and Alice’s legitimate access remained functional.', evidence
    except Incomplete as error:
        return 'incomplete', str(error), evidence
    finally:
        evidence['request_count'] = client.count
        await client.close()
