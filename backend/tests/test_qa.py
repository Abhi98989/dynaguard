import json
from pathlib import Path
import tempfile
import unittest
from dynaguard.qa import QAProfile, catalog, build_plan, TECHNIQUES
from dynaguard.cli import main


def profile():
    return QAProfile(project='Pilot', build_id='build-1', capabilities=['web', 'api', 'database'], workflows=[{'id':'minor','name':'Presentation','risk':'low','roles':['member'],'expected_rules':['Label is readable.']},{'id':'critical','name':'Private record','risk':'critical','roles':['owner','member'],'expected_rules':['Unrelated member cannot read the record.']}])


class QATests(unittest.TestCase):
    def test_catalog_unique_and_explicit_execution_gaps(self):
        skills = catalog()['skills']
        self.assertEqual(len(skills), 43)
        self.assertEqual(len({s['id'] for s in skills}), 43)
        self.assertTrue(all(s['checks'] and s['evidence_required'] and s['prerequisites'] for s in skills))
        self.assertTrue(all(s['implementation'] in ('planned','partial') for s in skills))
        self.assertEqual(len(TECHNIQUES), 14)

    def test_risk_order_applicability_and_no_false_pass(self):
        plan = build_plan(profile())
        self.assertEqual(plan['workflow_design_tasks'][0]['id'], 'critical')
        self.assertNotIn('hardware', {s['id'] for s in plan['selected_skills']})
        self.assertIn('hardware', plan['not_applicable_skills'])
        self.assertEqual(plan['status'], 'not_evaluated')
        self.assertEqual(plan['release_gate']['decision'], 'not_evaluated')
        self.assertEqual(plan['coverage']['executed_checks'], 0)
        self.assertEqual(plan['executions'], [])
        self.assertTrue(all(s['test_status']=='not_run' for s in plan['selected_skills']))

    def test_omitted_skills_visible(self):
        p=profile(); p.selected_skills=['permissions']
        plan=build_plan(p)
        self.assertEqual(plan['coverage']['selected_skills'],1)
        self.assertIn('workflow',plan['omitted_applicable_skills'])

    def test_unknown_inapplicable_and_duplicate_selections_rejected(self):
        for selection in (['does-not-exist'], ['hardware']):
            p=profile(); p.selected_skills=selection
            with self.assertRaises(ValueError): build_plan(p)
        value=profile().model_dump(); value['selected_skills']=['source','source']
        with self.assertRaises(ValueError): QAProfile.model_validate(value)
        value=profile().model_dump(); value['workflows'][1]['id']='minor'
        with self.assertRaises(ValueError): QAProfile.model_validate(value)

    def test_cli_plan_does_not_execute_tests(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'profile.json'; output=Path(d)/'plan.json'
            source.write_text(profile().model_dump_json())
            self.assertEqual(main(['qa','plan','--profile',str(source),'--output',str(output)]),0)
            self.assertEqual(json.loads(output.read_text())['coverage']['executed_checks'],0)
