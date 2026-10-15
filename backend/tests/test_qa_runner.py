"""Tests for executable QA test runner, assertions, state immutability, and regression retesting."""
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from dynaguard.qa_runner import (
    QATestSuite, ApiTestCase, ApiAssertion, BrowserTestCase, BrowserAction,
    execute_qa_suite, evaluate_assertion
)


class TestQARunner(unittest.TestCase):
    def test_evaluate_assertion(self):
        self.assertTrue(evaluate_assertion(200, 'equals', 200)[0])
        self.assertFalse(evaluate_assertion(400, 'equals', 200)[0])
        self.assertTrue(evaluate_assertion('hello world', 'contains', 'world')[0])
        self.assertFalse(evaluate_assertion('hello world', 'contains', 'bye')[0])
        self.assertTrue(evaluate_assertion('user_123', 'matches', r'^user_\d+$')[0])
        self.assertTrue(evaluate_assertion(15, 'greater_than', 10)[0])
        self.assertFalse(evaluate_assertion(5, 'greater_than', 10)[0])
        self.assertTrue(evaluate_assertion('any', 'exists', True)[0])
        self.assertFalse(evaluate_assertion(None, 'exists', True)[0])
        self.assertTrue(evaluate_assertion(100, 'type', 'int')[0])

    def test_suite_validation_unique_ids(self):
        with self.assertRaises(ValueError):
            QATestSuite(
                suite_id='suite-1',
                project='demo',
                build_id='b1',
                target_origin='http://localhost:8000',
                api_tests=[
                    ApiTestCase(id='test-1', name='T1', endpoint='/a', expected_status=200),
                    ApiTestCase(id='test-1', name='Duplicate', endpoint='/b', expected_status=200)
                ]
            )

    @patch('httpx.AsyncClient.request')
    def test_api_functional_happy_path(self, mock_request):
        # Mock 200 OK with expected JSON payload
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'status': 'success',
            'data': {'id': 42, 'role': 'editor', 'active': True}
        }
        mock_request.return_value = mock_resp

        suite = QATestSuite(
            suite_id='suite-test',
            project='HamroBuzz',
            build_id='build-100',
            target_origin='https://api.hamrobuzz.com',
            api_tests=[
                ApiTestCase(
                    id='api-auth-editor',
                    name='Verify editor profile access',
                    technique='happy_path',
                    endpoint='/api/profile',
                    method='GET',
                    expected_status=200,
                    assertions=[
                        ApiAssertion(field='status', operator='equals', expected='success'),
                        ApiAssertion(field='data.role', operator='equals', expected='editor'),
                        ApiAssertion(field='data.id', operator='greater_than', expected=0)
                    ]
                )
            ]
        )

        result = execute_qa_suite(suite)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['coverage']['planned'], 1)
        self.assertEqual(result['coverage']['passed'], 1)
        self.assertEqual(result['coverage']['failed'], 0)
        self.assertEqual(result['release_gate']['decision'], 'ready_for_release')
        self.assertEqual(len(result['findings']), 0)

    @patch('httpx.AsyncClient.get')
    @patch('httpx.AsyncClient.request')
    def test_negative_boundary_with_state_immutability(self, mock_request, mock_get):
        # 1. Mutation request is rejected with 422
        mock_mutation_resp = MagicMock()
        mock_mutation_resp.status_code = 422
        mock_mutation_resp.json.return_value = {'error': 'Validation failed: title cannot be empty'}
        mock_request.return_value = mock_mutation_resp

        # 2. State verification GET confirms original title is still intact ('Original Title')
        mock_state_resp = MagicMock()
        mock_state_resp.status_code = 200
        mock_state_resp.json.return_value = {'id': 10, 'title': 'Original Title'}
        mock_get.return_value = mock_state_resp

        suite = QATestSuite(
            suite_id='suite-boundary',
            project='NexaEDU',
            build_id='build-201',
            target_origin='https://nexaedu.test',
            api_tests=[
                ApiTestCase(
                    id='neg-empty-title',
                    name='Negative test: reject empty course title without altering state',
                    technique='negative',
                    endpoint='/api/courses/10',
                    method='PUT',
                    body={'title': ''},
                    expected_status=422,
                    assertions=[
                        ApiAssertion(field='error', operator='contains', expected='Validation failed')
                    ],
                    verify_state_unchanged={
                        'endpoint': '/api/courses/10',
                        'field': 'title',
                        'expected': 'Original Title'
                    }
                )
            ]
        )

        result = execute_qa_suite(suite)
        self.assertEqual(result['coverage']['passed'], 1)
        self.assertEqual(result['coverage']['failed'], 0)
        self.assertEqual(result['release_gate']['decision'], 'ready_for_release')

    @patch('httpx.AsyncClient.request')
    def test_defect_detection_and_retest_flow(self, mock_request):
        # Step 1: Run 1 fails due to unexpected 500 internal server error
        mock_fail_resp = MagicMock()
        mock_fail_resp.status_code = 500
        mock_fail_resp.json.return_value = {'error': 'Database crash'}
        mock_request.return_value = mock_fail_resp

        suite_failing = QATestSuite(
            suite_id='suite-regression',
            project='PrayasshPOS',
            build_id='build-v1-buggy',
            target_origin='https://pos.test',
            api_tests=[
                ApiTestCase(
                    id='api-checkout-tax',
                    name='Tax calculation invariant',
                    technique='invariants',
                    endpoint='/api/pos/checkout',
                    method='POST',
                    body={'items': [{'id': 1, 'qty': 2, 'price': 100}]},
                    expected_status=200,
                    assertions=[ApiAssertion(field='tax', operator='equals', expected=26.0)]
                )
            ]
        )

        run1 = execute_qa_suite(suite_failing)
        self.assertEqual(run1['coverage']['failed'], 1)
        self.assertEqual(run1['release_gate']['decision'], 'rejected')
        self.assertEqual(len(run1['findings']), 1)
        self.assertEqual(run1['findings'][0]['verification'], 'reproduced_defect')

        # Step 2: Build is fixed; run 2 executes with retest_of linked
        mock_pass_resp = MagicMock()
        mock_pass_resp.status_code = 200
        mock_pass_resp.json.return_value = {'order_id': 'ord-99', 'tax': 26.0}
        mock_request.return_value = mock_pass_resp

        suite_fixed = QATestSuite(
            suite_id='suite-regression',
            project='PrayasshPOS',
            build_id='build-v2-fixed',
            target_origin='https://pos.test',
            api_tests=[
                ApiTestCase(
                    id='api-checkout-tax',
                    name='Tax calculation invariant',
                    technique='invariants',
                    endpoint='/api/pos/checkout',
                    method='POST',
                    body={'items': [{'id': 1, 'qty': 2, 'price': 100}]},
                    expected_status=200,
                    assertions=[ApiAssertion(field='tax', operator='equals', expected=26.0)]
                )
            ]
        )

        run2 = execute_qa_suite(suite_fixed, retest_of_report=run1)
        self.assertEqual(run2['retest_of'], run1['run_id'])
        self.assertEqual(run2['coverage']['passed'], 1)
        self.assertEqual(run2['coverage']['failed'], 0)
        self.assertEqual(run2['release_gate']['decision'], 'ready_for_release')
        self.assertEqual(run2['executions'][0]['retest_status'], 'verified_fixed')


if __name__ == '__main__':
    unittest.main()
