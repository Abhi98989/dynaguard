"""Risk-based QA planning. This module does not execute test adapters."""
import hashlib
from importlib.resources import files
import json
from typing import Literal
from pydantic import Field, model_validator
from .config import Strict
from .engine import report_base, seal_report

Capability = Literal['web', 'api', 'mobile', 'database', 'payments', 'offline', 'ai', 'search', 'files', 'messaging', 'hardware', 'saas']


class Workflow(Strict):
    id: str = Field(pattern=r'^[a-zA-Z0-9_.-]{1,80}$')
    name: str = Field(min_length=1, max_length=160)
    risk: Literal['critical', 'high', 'medium', 'low']
    roles: list[str] = Field(min_length=1, max_length=20)
    expected_rules: list[str] = Field(min_length=1, max_length=20)


class QAProfile(Strict):
    version: Literal[1] = 1
    project: str = Field(min_length=1, max_length=120)
    build_id: str = Field(min_length=1, max_length=120)
    capabilities: list[Capability] = Field(min_length=1, max_length=12)
    workflows: list[Workflow] = Field(min_length=1, max_length=100)
    selected_skills: list[str] | None = Field(default=None, min_length=1, max_length=43)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({w.id for w in self.workflows}) != len(self.workflows):
            raise ValueError('Workflow IDs must be unique')
        if self.selected_skills and len(set(self.selected_skills)) != len(self.selected_skills):
            raise ValueError('Skill IDs must be unique')
        return self


def catalog():
    return json.loads(files('dynaguard').joinpath('data/qa_catalog.json').read_text(encoding='utf-8'))


TECHNIQUES = [
    {'id': 'happy_path', 'instruction': 'Define representative valid inputs and verify the complete expected business result.'},
    {'id': 'negative', 'instruction': 'Define invalid/missing inputs and prove rejection leaves no unintended state changes.'},
    {'id': 'boundaries', 'instruction': 'List actual business limits; test just below, at and above each limit where applicable.'},
    {'id': 'decision_table', 'instruction': 'List role, state and input conditions; test meaningful allowed and forbidden combinations.'},
    {'id': 'state_transitions', 'instruction': 'Map valid states and transitions; attempt invalid, repeated and out-of-order transitions.'},
    {'id': 'invariants', 'instruction': 'Define facts that must remain true across all operations; compare authoritative before/after state.'},
    {'id': 'pairwise', 'instruction': 'Reduce large browser/device/input combinations with documented pairwise coverage; explicitly add high-risk combinations.'},
    {'id': 'failure_recovery', 'instruction': 'Select relevant interruption/failure points and specify recovery expectations before injecting faults in isolation.'},
    {'id': 'exploratory', 'instruction': 'Write a time-boxed charter, record observations and convert confirmed defects into regression tests.'},
    {'id': 'differential', 'instruction': 'Compare old/new versions against the same approved fixtures; investigate differences rather than assuming the old version is correct.'},
    {'id': 'metamorphic', 'instruction': 'Define an approved relationship between related inputs and outputs, then verify it; do not invent business invariants.'},
    {'id': 'mutation', 'instruction': 'In a disposable code checkout, mutate selected logic to assess whether tests detect defects; review equivalent and surviving mutants.'},
    {'id': 'bounded_fuzzing', 'instruction': 'Generate bounded schema-aware cases in an isolated test environment; retain seeds and minimized reproductions with no real data.'},
    {'id': 'regression', 'instruction': 'Include prior failures and changed dependencies; record flaky attempts without hiding them through retries.'},
]


def build_plan(profile):
    data = catalog()
    known = {s['id']: s for s in data['skills']}
    applicable = {s['id'] for s in data['skills'] if '*' in s['applies_to'] or set(profile.capabilities).intersection(s['applies_to'])}
    selected = set(profile.selected_skills) if profile.selected_skills is not None else applicable
    unknown = selected - set(known)
    if unknown:
        raise ValueError('Unknown skill IDs')
    if selected - applicable:
        raise ValueError('Selected skill is not applicable to declared capabilities')
    result = report_base('qa_plan', profile.project)
    result.update(status='not_evaluated', build_id=profile.build_id, catalog_version=data['catalog_version'])
    result['profile_sha256'] = hashlib.sha256(profile.model_dump_json().encode()).hexdigest()
    result['selected_skills'] = [dict(s, test_status='not_run') for s in data['skills'] if s['id'] in selected]
    result['omitted_applicable_skills'] = sorted(applicable - selected)
    result['not_applicable_skills'] = sorted(set(known) - applicable)
    risk_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    result['workflow_design_tasks'] = [
        {**workflow.model_dump(), 'status': 'design_required', 'techniques': TECHNIQUES,
         'next_action': 'Turn relevant techniques into executable test cases with concrete inputs, assertions, fixtures, cleanup and evidence.'}
        for workflow in sorted(profile.workflows, key=lambda w: (risk_order[w.risk], w.id))
    ]
    result['release_gate'] = {
        'decision': 'not_evaluated',
        'reason': 'Planning does not execute checks or establish release readiness.',
        'proposed_rules': [
            'Required failed, blocked, incomplete, not-run or flaky checks block a passing release assessment.',
            'Every required result must identify the tested build, test version, environment, evidence and expected outcome.',
            'Unverified findings require triage; they are not automatically confirmed defects.',
            'Manual acceptance and accessibility observations require a recorded human reviewer.',
            'Omitted applicable skills and accepted exceptions must remain visible with rationale and owner.',
            'A passing configured suite is limited to its declared scope; it is not proof of complete quality.'
        ]
    }
    result['coverage'] = {'catalog_skills': len(known), 'selected_skills': len(selected), 'omitted_applicable_skills': len(applicable-selected), 'workflows': len(profile.workflows), 'executed_checks': 0}
    result['limitations'] = [
        'This output is a QA plan and skill contract catalog, not a test execution report.',
        'Partial adapters cover only existing documented checks; most skill executors are not implemented.',
        'Applicability depends on declared capabilities; missing product information can leave coverage gaps.',
        'A senior QA engineer or product owner must confirm expected behavior and high-risk scenarios.'
    ]
    return seal_report(result)
