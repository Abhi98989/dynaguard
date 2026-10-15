import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import api, audit_api
from app.models import Base, Project, UploadToken
from app.security import COOKIE, signer


class TestAuditAPI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            'sqlite:///' + (Path(self.temp.name) / 'audit_test.db').as_posix(),
            connect_args={'check_same_thread': False}
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(self.engine, expire_on_commit=False)

        self.env = patch.dict(os.environ, {
            'SESSION_SECRET': 'test-session-secret-key-at-least-32-chars-long',
            'ADMIN_PASSWORD_HASH': '00:00'
        })
        self.env.start()

        self.api_patch = patch.object(api, 'Session', self.session)
        self.audit_api_patch = patch.object(audit_api, 'Session', self.session)
        self.api_patch.start()
        self.audit_api_patch.start()

        self.client = TestClient(api.app)
        self.auth_cookie = signer().dumps('administrator')

        with self.session() as s:
            proj = Project(name='Audit Test Project')
            s.add(proj)
            s.commit()
            self.project_id = proj.id

    def tearDown(self):
        self.client.close()
        self.api_patch.stop()
        self.audit_api_patch.stop()
        self.env.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def test_token_creation_and_revocation(self):
        # 1. Create token
        resp = self.client.post(
            f'/projects/{self.project_id}/upload-tokens',
            json={'name': 'CI Token'},
            cookies={COOKIE: self.auth_cookie},
            headers={'x-dynaguard-client': 'dashboard'}
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        token = data['token']
        token_id = data['id']
        self.assertTrue(token.startswith('dgt_'))

        # 2. List tokens
        list_resp = self.client.get(
            f'/projects/{self.project_id}/upload-tokens',
            cookies={COOKIE: self.auth_cookie},
            headers={'x-dynaguard-client': 'dashboard'}
        )
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()), 1)

        # 3. Ingest report with token
        report = {
            'schema_version': 2,
            'mode': 'audit',
            'project': 'Test App',
            'status': 'completed',
            'stacks': ['laravel'],
            'summary': {'critical': 0, 'high': 1, 'medium': 0, 'low': 0, 'info': 0},
            'by_layer': {'code': 1},
            'coverage': [],
            'findings': [{
                'id': 'abc123',
                'rule_id': 'laravel.mass-assignment',
                'tool': 'builtin',
                'layer': 'function',
                'title': 'Mass assignment vulnerability',
                'severity': 'high',
                'confidence': 'high',
                'verification': 'suspected',
                'path': 'app/User.php',
                'line': 12,
                'cwe': 'CWE-915',
                'owasp': None,
                'recommendation': 'Use $fillable',
                'evidence': 'Pattern matched'
            }],
            'suppressed': 0,
            'limitations': []
        }
        ingest_resp = self.client.post(
            '/ingest/audit-reports',
            json=report,
            headers={
                'Authorization': f'Bearer {token}',
                'x-dynaguard-client': 'dashboard'
            }
        )
        self.assertEqual(ingest_resp.status_code, 201)
        self.assertEqual(ingest_resp.json()['project_id'], self.project_id)
        self.assertEqual(ingest_resp.json()['findings_count'], 1)

        # 4. Revoke token
        rev_resp = self.client.post(
            f'/upload-tokens/{token_id}/revoke',
            cookies={COOKIE: self.auth_cookie},
            headers={'x-dynaguard-client': 'dashboard'}
        )
        self.assertEqual(rev_resp.status_code, 200)

        # 5. Ingest should now fail with 401
        failed_ingest = self.client.post(
            '/ingest/audit-reports',
            json=report,
            headers={
                'Authorization': f'Bearer {token}',
                'x-dynaguard-client': 'dashboard'
            }
        )
        self.assertEqual(failed_ingest.status_code, 401)


if __name__ == '__main__':
    unittest.main()
