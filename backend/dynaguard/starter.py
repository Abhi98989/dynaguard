def starter():
    return {
        'version': 1, 'project': 'Local pilot', 'build_id': 'fixture-v1',
        'target': {'origin': 'http://127.0.0.1:8101', 'pinned_ips': ['127.0.0.1'], 'allow_private': True, 'allowed_paths': ['/login', '/records/record-a', '/records/record-b']},
        'identities': {
            'alice': {'kind': 'json_login', 'login_path': '/login', 'username': 'alice', 'password_env': 'FIXTURE_PASSWORD', 'auth_check': {'path': '/records/record-a', 'expected': {'id': 'record-a', 'owner_id': 'alice'}}},
            'bob': {'kind': 'json_login', 'login_path': '/login', 'username': 'bob', 'password_env': 'FIXTURE_PASSWORD', 'auth_check': {'path': '/records/record-b', 'expected': {'id': 'record-b', 'owner_id': 'bob'}}},
            'anonymous': {'kind': 'anonymous'}
        },
        'tests': [
            {'id': 'records.cross-owner', 'title': 'Another user can read the designated record', 'authorized_identity': 'bob', 'probe_identity': 'alice', 'resource': {'path': '/records/record-b', 'expected': {'id': 'record-b', 'owner_id': 'bob', 'marker': 'synthetic-bob-942'}}},
            {'id': 'records.anonymous', 'title': 'Anonymous access to designated record', 'authorized_identity': 'bob', 'probe_identity': 'anonymous', 'resource': {'path': '/records/record-b', 'expected': {'id': 'record-b', 'owner_id': 'bob', 'marker': 'synthetic-bob-942'}}}
        ]
    }
