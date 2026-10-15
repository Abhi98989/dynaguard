"""Executable QA test runner supporting API functional testing, browser workflow verification, evidence capture, and regression retesting."""
import asyncio
import base64
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
import httpx
from pydantic import Field, model_validator
from .config import Strict
from .engine import field as get_field, mask, seal_report
from .qa import QAProfile

AssertionOperator = Literal[
    'equals', 'not_equals', 'contains', 'matches', 'type', 'exists', 'greater_than', 'less_than'
]

TechniqueType = Literal[
    'happy_path', 'negative', 'boundaries', 'decision_table',
    'state_transitions', 'invariants', 'pairwise', 'regression', 'bounded_fuzzing'
]


class ApiAssertion(Strict):
    field: str | None = None  # None checks entire body, or dot-separated e.g. "user.id"
    operator: AssertionOperator = 'equals'
    expected: Any = None


class ApiTestCase(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_.-]{1,80}$')
    name: str = Field(min_length=1, max_length=160)
    technique: TechniqueType = 'happy_path'
    workflow_id: str | None = None
    skill_id: str | None = None
    method: Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE'] = 'GET'
    endpoint: str = Field(min_length=1, max_length=500)
    auth_role: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] | None = None
    body: Any | None = None
    expected_status: int = 200
    assertions: list[ApiAssertion] = Field(default_factory=list)
    # Negative/boundary testing invariant check: verify rejected mutation did not alter state
    verify_state_unchanged: dict[str, Any] | None = None


class BrowserAction(Strict):
    type: Literal['navigate', 'fill', 'click', 'select', 'wait_for', 'assert_text', 'assert_visible', 'assert_not_visible', 'screenshot']
    selector: str | None = None
    value: str | None = None
    timeout_ms: int = 5000


class BrowserTestCase(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_.-]{1,80}$')
    name: str = Field(min_length=1, max_length=160)
    technique: TechniqueType = 'happy_path'
    workflow_id: str | None = None
    skill_id: str | None = None
    start_url: str = Field(min_length=1, max_length=500)
    auth_role: str | None = None
    actions: list[BrowserAction] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)


class QATestSuite(Strict):
    version: Literal[1] = 1
    suite_id: str = Field(min_length=1, max_length=80)
    project: str = Field(min_length=1, max_length=120)
    build_id: str = Field(min_length=1, max_length=120)
    target_origin: str = Field(min_length=1, max_length=500)
    identities: dict[str, dict[str, Any]] = Field(default_factory=dict)
    api_tests: list[ApiTestCase] = Field(default_factory=list)
    browser_tests: list[BrowserTestCase] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_test_ids(self):
        all_ids = [t.id for t in self.api_tests] + [t.id for t in self.browser_tests]
        if len(set(all_ids)) != len(all_ids):
            raise ValueError('All test IDs within a QA suite must be unique')
        return self


def evaluate_assertion(actual_value: Any, op: AssertionOperator, expected_value: Any) -> tuple[bool, str]:
    if op == 'equals':
        matched = actual_value == expected_value
        return matched, f"Expected {expected_value!r}, got {actual_value!r}"
    if op == 'not_equals':
        matched = actual_value != expected_value
        return matched, f"Expected value not to equal {expected_value!r}, got {actual_value!r}"
    if op == 'contains':
        matched = expected_value in actual_value if actual_value is not None else False
        return matched, f"Expected {actual_value!r} to contain {expected_value!r}"
    if op == 'matches':
        matched = bool(re.search(str(expected_value), str(actual_value)))
        return matched, f"Expected {actual_value!r} to match regex {expected_value!r}"
    if op == 'type':
        expected_type_str = str(expected_value).lower()
        actual_type_str = type(actual_value).__name__.lower()
        matched = actual_type_str == expected_type_str
        return matched, f"Expected type {expected_type_str}, got {actual_type_str}"
    if op == 'exists':
        matched = (actual_value is not None) == bool(expected_value)
        return matched, f"Expected exists={expected_value}, got {actual_value is not None}"
    if op == 'greater_than':
        try:
            matched = float(actual_value) > float(expected_value)
        except (ValueError, TypeError):
            matched = False
        return matched, f"Expected {actual_value} > {expected_value}"
    if op == 'less_than':
        try:
            matched = float(actual_value) < float(expected_value)
        except (ValueError, TypeError):
            matched = False
        return matched, f"Expected {actual_value} < {expected_value}"
    return False, f"Unknown operator {op}"


async def run_api_test(test: ApiTestCase, suite: QATestSuite, client: httpx.AsyncClient, secrets: list[str]) -> dict[str, Any]:
    start_time = time.time()
    url = suite.target_origin.rstrip('/') + '/' + test.endpoint.lstrip('/')
    headers = dict(test.headers)

    # Attach authentication for specified role
    if test.auth_role:
        identity = suite.identities.get(test.auth_role)
        if not identity:
            return {
                'test_id': test.id,
                'name': test.name,
                'type': 'api',
                'technique': test.technique,
                'outcome': 'blocked',
                'actual': f"Configured auth_role '{test.auth_role}' not defined in suite identities",
                'duration_ms': 0,
                'evidence': []
            }
        if 'token' in identity:
            headers['Authorization'] = f"Bearer {identity['token']}"
        if 'api_key' in identity:
            headers['X-API-Key'] = identity['api_key']
        if 'headers' in identity and isinstance(identity['headers'], dict):
            headers.update(identity['headers'])

    evidence_steps = []
    try:
        response = await client.request(
            method=test.method,
            url=url,
            headers=headers,
            params=test.params,
            json=test.body if test.body is not None and not isinstance(test.body, (str, bytes)) else None,
            content=test.body if isinstance(test.body, (str, bytes)) else None,
            timeout=15.0
        )
        duration_ms = int((time.time() - start_time) * 1000)

        # Parse response body
        resp_data = None
        try:
            resp_data = response.json()
        except Exception:
            resp_data = response.text[:2000]

        step_ev = {
            'step': 'http_request',
            'method': test.method,
            'url': url,
            'status_code': response.status_code,
            'duration_ms': duration_ms,
            'response_snippet': mask(resp_data, secrets)
        }
        evidence_steps.append(step_ev)

        # 1. Assert status code
        if response.status_code != test.expected_status:
            return {
                'test_id': test.id,
                'name': test.name,
                'type': 'api',
                'technique': test.technique,
                'outcome': 'failed',
                'actual': f"Expected status {test.expected_status}, received {response.status_code}",
                'duration_ms': duration_ms,
                'evidence': evidence_steps
            }

        # 2. Evaluate assertions
        for assertion in test.assertions:
            actual_val = get_field(resp_data, assertion.field) if assertion.field else resp_data
            matched, msg = evaluate_assertion(actual_val, assertion.operator, assertion.expected)
            evidence_steps.append({
                'step': 'assertion',
                'field': assertion.field,
                'operator': assertion.operator,
                'expected': assertion.expected,
                'matched': matched,
                'detail': msg
            })
            if not matched:
                return {
                    'test_id': test.id,
                    'name': test.name,
                    'type': 'api',
                    'technique': test.technique,
                    'outcome': 'failed',
                    'actual': f"Assertion failed: {msg}",
                    'duration_ms': duration_ms,
                    'evidence': evidence_steps
                }

        # 3. State-immutability verification (for negative/boundary tests)
        if test.verify_state_unchanged:
            v_endpoint = test.verify_state_unchanged.get('endpoint')
            v_field = test.verify_state_unchanged.get('field')
            v_expected = test.verify_state_unchanged.get('expected')
            if v_endpoint:
                v_url = suite.target_origin.rstrip('/') + '/' + v_endpoint.lstrip('/')
                v_resp = await client.get(v_url, headers=headers, timeout=10.0)
                try:
                    v_data = v_resp.json()
                except Exception:
                    v_data = v_resp.text
                v_actual = get_field(v_data, v_field) if v_field else v_data
                state_held = v_actual == v_expected
                evidence_steps.append({
                    'step': 'verify_state_unchanged',
                    'endpoint': v_endpoint,
                    'field': v_field,
                    'expected': v_expected,
                    'actual': v_actual,
                    'preserved': state_held
                })
                if not state_held:
                    return {
                        'test_id': test.id,
                        'name': test.name,
                        'type': 'api',
                        'technique': test.technique,
                        'outcome': 'failed',
                        'actual': f"State immutability invariant violated: field '{v_field}' changed to {v_actual!r} despite rejected operation",
                        'duration_ms': duration_ms,
                        'evidence': evidence_steps
                    }

        return {
            'test_id': test.id,
            'name': test.name,
            'type': 'api',
            'technique': test.technique,
            'outcome': 'passed',
            'actual': f"HTTP {response.status_code} matched assertions; state verified",
            'duration_ms': duration_ms,
            'evidence': evidence_steps
        }

    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            'test_id': test.id,
            'name': test.name,
            'type': 'api',
            'technique': test.technique,
            'outcome': 'failed',
            'actual': f"Connection / execution error: {str(exc)}",
            'duration_ms': duration_ms,
            'evidence': evidence_steps
        }


async def run_browser_test(test: BrowserTestCase, suite: QATestSuite, secrets: list[str]) -> dict[str, Any]:
    start_time = time.time()
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {
            'test_id': test.id,
            'name': test.name,
            'type': 'browser',
            'technique': test.technique,
            'outcome': 'incomplete',
            'actual': 'Playwright browser automation driver is not installed in the environment (never converted to pass)',
            'duration_ms': 0,
            'evidence': []
        }

    evidence = []
    console_errors = []
    network_failures = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()

            page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
            page.on('requestfailed', lambda req: network_failures.append(f"{req.method} {req.url}: {req.failure}"))

            target_url = test.start_url
            if not target_url.startswith(('http://', 'https://')):
                target_url = suite.target_origin.rstrip('/') + '/' + test.start_url.lstrip('/')

            await page.goto(target_url, timeout=15000, wait_until='domcontentloaded')
            evidence.append({'step': 'goto', 'url': target_url, 'title': await page.title()})

            for action in test.actions:
                act_start = time.time()
                timeout = action.timeout_ms

                if action.type == 'navigate':
                    dest = action.value or target_url
                    if not dest.startswith(('http://', 'https://')):
                        dest = suite.target_origin.rstrip('/') + '/' + dest.lstrip('/')
                    await page.goto(dest, timeout=timeout)
                    evidence.append({'action': 'navigate', 'url': dest})

                elif action.type == 'fill':
                    if not action.selector:
                        raise ValueError('Selector required for fill action')
                    await page.wait_for_selector(action.selector, timeout=timeout)
                    await page.fill(action.selector, action.value or '')
                    evidence.append({'action': 'fill', 'selector': action.selector, 'value': mask(action.value, secrets)})

                elif action.type == 'click':
                    if not action.selector:
                        raise ValueError('Selector required for click action')
                    await page.wait_for_selector(action.selector, timeout=timeout)
                    await page.click(action.selector)
                    evidence.append({'action': 'click', 'selector': action.selector})

                elif action.type == 'select':
                    if not action.selector:
                        raise ValueError('Selector required for select action')
                    await page.select_option(action.selector, action.value)
                    evidence.append({'action': 'select', 'selector': action.selector, 'value': action.value})

                elif action.type == 'wait_for':
                    if not action.selector:
                        raise ValueError('Selector required for wait_for action')
                    await page.wait_for_selector(action.selector, timeout=timeout)
                    evidence.append({'action': 'wait_for', 'selector': action.selector})

                elif action.type == 'assert_text':
                    if not action.selector:
                        raise ValueError('Selector required for assert_text action')
                    await page.wait_for_selector(action.selector, timeout=timeout)
                    text = await page.text_content(action.selector) or ''
                    if (action.value or '') not in text:
                        raise AssertionError(f"Expected text '{action.value}' not found in selector '{action.selector}'. Actual: '{text.strip()}'")
                    evidence.append({'action': 'assert_text', 'selector': action.selector, 'found': True})

                elif action.type == 'assert_visible':
                    if not action.selector:
                        raise ValueError('Selector required for assert_visible action')
                    is_vis = await page.is_visible(action.selector)
                    if not is_vis:
                        raise AssertionError(f"Element '{action.selector}' is not visible on page")
                    evidence.append({'action': 'assert_visible', 'selector': action.selector, 'visible': True})

                elif action.type == 'assert_not_visible':
                    if not action.selector:
                        raise ValueError('Selector required for assert_not_visible action')
                    is_vis = await page.is_visible(action.selector)
                    if is_vis:
                        raise AssertionError(f"Element '{action.selector}' is unexpectedly visible on page")
                    evidence.append({'action': 'assert_not_visible', 'selector': action.selector, 'hidden': True})

                elif action.type == 'screenshot':
                    png = await page.screenshot()
                    b64 = base64.b64encode(png).decode('ascii')
                    evidence.append({'action': 'screenshot', 'bytes': len(png), 'base64_preview': b64[:80] + '...'})

            await browser.close()

        duration_ms = int((time.time() - start_time) * 1000)
        return {
            'test_id': test.id,
            'name': test.name,
            'type': 'browser',
            'technique': test.technique,
            'outcome': 'passed',
            'actual': f"All {len(test.actions)} browser workflow actions and DOM assertions succeeded",
            'duration_ms': duration_ms,
            'evidence': evidence,
            'console_errors': console_errors,
            'network_failures': network_failures
        }

    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            'test_id': test.id,
            'name': test.name,
            'type': 'browser',
            'technique': test.technique,
            'outcome': 'failed',
            'actual': f"Browser workflow step failed: {str(exc)}",
            'duration_ms': duration_ms,
            'evidence': evidence,
            'console_errors': console_errors,
            'network_failures': network_failures
        }


async def execute_qa_suite_async(
    suite: QATestSuite,
    profile: QAProfile | None = None,
    retest_of_report: dict[str, Any] | None = None
) -> dict[str, Any]:
    run_id = str(uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    # Extract secrets to mask from identities
    secrets = []
    for ident in suite.identities.values():
        if isinstance(ident, dict):
            for k, v in ident.items():
                if isinstance(v, str) and len(v) >= 4 and k in ('password', 'token', 'key', 'secret', 'api_key'):
                    secrets.append(v)

    executions = []
    findings = []

    # Map previous failures if this is a regression retest
    previous_results = {}
    if retest_of_report and 'executions' in retest_of_report:
        for prev in retest_of_report['executions']:
            previous_results[prev['test_id']] = prev

    async with httpx.AsyncClient(verify=False) as client:
        # 1. Run API Tests
        for api_test in suite.api_tests:
            result = await run_api_test(api_test, suite, client, secrets)
            # Evaluate regression / retest status
            if api_test.id in previous_results:
                prev = previous_results[api_test.id]
                if prev.get('outcome') == 'failed' and result['outcome'] == 'passed':
                    result['retest_status'] = 'verified_fixed'
                    result['original_failure'] = prev.get('actual')
                elif prev.get('outcome') == 'failed' and result['outcome'] == 'failed':
                    result['retest_status'] = 'reproduced_defect'
                    result['original_failure'] = prev.get('actual')
                else:
                    result['retest_status'] = 'retest_unchanged'

            if result['outcome'] == 'failed':
                findings.append({
                    'id': hashlib.sha256(f"{suite.project}:{api_test.id}:{suite.build_id}".encode()).hexdigest()[:16],
                    'test_id': api_test.id,
                    'title': f"Defect in API test '{api_test.name}': {result['actual']}",
                    'severity': 'high' if api_test.technique in ('invariants', 'negative') else 'medium',
                    'technique': api_test.technique,
                    'verification': 'reproduced_defect',
                    'recommendation': f"Investigate {api_test.method} {api_test.endpoint}; verify state invariant and assertions."
                })
            executions.append(result)

        # 2. Run Browser Tests
        for browser_test in suite.browser_tests:
            result = await run_browser_test(browser_test, suite, secrets)
            if browser_test.id in previous_results:
                prev = previous_results[browser_test.id]
                if prev.get('outcome') == 'failed' and result['outcome'] == 'passed':
                    result['retest_status'] = 'verified_fixed'
                elif prev.get('outcome') == 'failed' and result['outcome'] == 'failed':
                    result['retest_status'] = 'reproduced_defect'

            if result['outcome'] == 'failed':
                findings.append({
                    'id': hashlib.sha256(f"{suite.project}:{browser_test.id}:{suite.build_id}".encode()).hexdigest()[:16],
                    'test_id': browser_test.id,
                    'title': f"Defect in browser workflow '{browser_test.name}': {result['actual']}",
                    'severity': 'high',
                    'technique': browser_test.technique,
                    'verification': 'reproduced_defect',
                    'recommendation': f"Verify page {browser_test.start_url}; check console errors and DOM selectors."
                })
            executions.append(result)

    counts = {
        'planned': len(suite.api_tests) + len(suite.browser_tests),
        'passed': sum(1 for e in executions if e['outcome'] == 'passed'),
        'failed': sum(1 for e in executions if e['outcome'] == 'failed'),
        'blocked': sum(1 for e in executions if e['outcome'] == 'blocked'),
        'incomplete': sum(1 for e in executions if e['outcome'] == 'incomplete'),
        'skipped': sum(1 for e in executions if e['outcome'] == 'skipped'),
    }
    counts['executed_checks'] = counts['passed'] + counts['failed']

    # Release readiness assessment
    if counts['failed'] > 0:
        decision = 'rejected'
        reason = f"Release blocked: {counts['failed']} test(s) failed with reproducible defects."
    elif counts['blocked'] > 0 or counts['incomplete'] > 0:
        decision = 'rejected'
        reason = f"Release blocked: {counts['blocked'] + counts['incomplete']} check(s) were blocked or incomplete."
    elif counts['executed_checks'] == 0:
        decision = 'not_evaluated'
        reason = "No executable tests were configured or run."
    else:
        decision = 'ready_for_release'
        reason = f"All {counts['passed']} configured test checks passed with authoritative evidence."

    report = {
        'schema_version': 2,
        'mode': 'qa_execution',
        'run_id': run_id,
        'project': suite.project,
        'build_id': suite.build_id,
        'suite_id': suite.suite_id,
        'target_origin': suite.target_origin,
        'created_at': started_at,
        'status': 'completed' if counts['incomplete'] == 0 and counts['blocked'] == 0 else 'incomplete',
        'retest_of': retest_of_report.get('run_id') if retest_of_report else None,
        'release_gate': {
            'decision': decision,
            'reason': reason,
            'required_passed': counts['passed'],
            'defects_count': counts['failed']
        },
        'coverage': counts,
        'executions': executions,
        'findings': findings,
        'limitations': [
            'Test results apply strictly to the declared target origin and configured fixtures.',
            'Passing results certify verified checks, not the absence of undiscovered defects.',
            'Production release decisions require independent manual security and accessibility sign-off.'
        ]
    }

    return seal_report(mask(report, secrets))


def execute_qa_suite(
    suite: QATestSuite,
    profile: QAProfile | None = None,
    retest_of_report: dict[str, Any] | None = None
) -> dict[str, Any]:
    return asyncio.run(execute_qa_suite_async(suite, profile, retest_of_report))
