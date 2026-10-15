import asyncio
import json
import unittest
from unittest.mock import patch
import httpx
import test_acceptance
from test_engine import contract, handler, SECRET
from app import engine_api, engine_worker
from dynaguard.engine import verify


class EngineAdapterTests(unittest.TestCase):
    def setUp(self):
        test_acceptance.PlatformTests.setUp(self)
        self.extra = [patch.object(engine_api, 'Session', self.session), patch.object(engine_worker, 'Session', self.session), patch.dict('os.environ', {'DYNAGUARD_TEST_PASSWORD': SECRET, 'TARGETS_JSON': json.dumps({'http://127.0.0.1:8910': ['127.0.0.1']})})]
        for p in self.extra: p.start()
        self.project_id = self.client.post('/projects', json={'name': 'Adapter test'}).json()['id']

    def tearDown(self):
        for p in reversed(self.extra): p.stop()
        test_acceptance.PlatformTests.tearDown(self)

    def test_shared_engine_multiple_results(self):
        async def with_transport(config, progress):
            return await verify(config, progress, httpx.MockTransport(handler()))
        response = self.client.post(f'/projects/{self.project_id}/engine-runs', json={'mode': 'verify', 'config': contract().model_dump()})
        self.assertEqual(response.status_code, 201, response.text)
        with patch.object(engine_worker, 'verify', with_transport): asyncio.run(engine_worker.execute(*engine_worker.claim()))
        runs = self.client.get(f'/projects/{self.project_id}/engine-runs').json()
        self.assertEqual(runs[0]['status'], 'completed')
        self.assertEqual(len(runs[0]['report']['executions']), 2)
        self.assertEqual(len(runs[0]['report']['findings']), 1)
        self.assertNotIn(SECRET, json.dumps(runs))

    def test_scope_and_secret_names_rejected(self):
        value = contract().model_dump(); value['target']['pinned_ips'] = ['127.0.0.2']
        self.assertEqual(self.client.post(f'/projects/{self.project_id}/engine-runs', json={'mode': 'verify', 'config': value}).status_code, 422)
        value = contract().model_dump(); value['identities']['owner']['password_env'] = 'SESSION_SECRET'
        self.assertEqual(self.client.post(f'/projects/{self.project_id}/engine-runs', json={'mode': 'verify', 'config': value}).status_code, 422)

    def test_source_upload_masking_and_traversal(self):
        route = f'/projects/{self.project_id}/source-review'
        result = self.client.post(route, json={'files': [{'path': 'app.py', 'content': 'password = "'+SECRET+'"'}]})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(len(result.json()['report']['findings']), 1)
        self.assertNotIn(SECRET, result.text)
        self.assertEqual(self.client.post(route, json={'files': [{'path': '../escape.py', 'content': 'bad'}]}).status_code, 422)

    def test_queued_cancel(self):
        row = self.client.post(f'/projects/{self.project_id}/engine-runs', json={'mode': 'verify', 'config': contract().model_dump()}).json()
        self.assertEqual(self.client.post('/engine-runs/'+row['id']+'/cancel').json()['status'], 'cancelled')
        self.assertIsNone(engine_worker.claim())

    def test_running_cancel_stops_shared_engine_task(self):
        closed = []
        async def slow(config, progress):
            try:
                await asyncio.sleep(20)
            finally:
                closed.append(True)
        row = self.client.post(f'/projects/{self.project_id}/engine-runs', json={'mode': 'verify', 'config': contract().model_dump()}).json()
        job = engine_worker.claim()
        async def exercise():
            task = asyncio.create_task(engine_worker.execute(*job))
            await asyncio.sleep(0.2)
            self.client.post('/engine-runs/'+row['id']+'/cancel')
            await asyncio.wait_for(task, timeout=2)
        with patch.object(engine_worker, 'verify', slow): asyncio.run(exercise())
        runs = self.client.get(f'/projects/{self.project_id}/engine-runs').json()
        self.assertEqual(runs[0]['status'], 'cancelled')
        self.assertTrue(closed)
