import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.assessments import AssessmentWorkflow, ReviewRequired, canonical, digest, load_json, score_submission, verify_result
from app.local_api import create_app
from app.memory import MemoryStore
from scripts.assessment_fixtures import configuration, exports, install, row
from test_local_acceptance import local_settings


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.memory = MemoryStore(self.root / 'nexus_memory.sqlite3')
        self.model = AsyncMock()
        self.workflow = AssessmentWorkflow(self.memory, self.root / 'artifacts', self.model)
        install(self.workflow.root)
        roster, keys = configuration()
        self.bundle = {'roster': roster, 'keys': keys}

    def process(self, name, value):
        path = self.workflow.intake / name
        path.write_text(json.dumps(value), encoding='utf-8')
        self.workflow.scan()
        self.workflow.scan()
        self.workflow.run_one()
        job_id = digest(path.read_bytes())
        with self.memory._connect() as db:
            return dict(db.execute('SELECT * FROM assessment_jobs WHERE id=?', (job_id,)).fetchone())

    def test_scores_missing_records_and_matched_changes(self):
        for name, value in exports().items():
            self.assertEqual(self.process(name, value)['status'], 'completed')
        report = next(self.workflow.outputs.glob('cohort-*.json'))
        reports = [load_json(p.read_text()) for p in self.workflow.outputs.glob('cohort-*.json')]
        report = next(r for r in reports if r['assessment_id'] == 'synthetic-foundations')
        self.assertEqual(report['stages']['baseline']['mean_percent'], 50)
        self.assertEqual(report['stages']['final']['mean_percent'], 87.5)
        self.assertEqual(report['stages']['final']['missing_student_ids'], ['S003'])
        self.assertEqual(report['students'][0]['change_percentage_points']['baseline_to_final'], 75)
        self.assertEqual(report['students'][1]['recommended_foundation_work'], ['Practice counting in pairs to ten.'])
        self.model.complete.assert_not_called()

    def test_invalid_ids_missing_fields_and_conflicts_do_not_invent_results(self):
        valid = row('S001', 'baseline', ['4', '10', 'input', 'yes'])
        conflicting = row('S001', 'baseline', ['4', '8', 'input', 'yes'])
        unknown = row('UNKNOWN', 'baseline', ['4', '10', 'input', 'yes'])
        missing = {**valid, 'student_id': ''}
        job = self.process('bad.json', {'submissions': [valid, conflicting, unknown, missing]})
        self.assertEqual(job['status'], 'review')
        with self.memory._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_results').fetchone()[0], 0)
        for field in ('student_id', 'cohort', 'stage', 'answer_key', 'answers'):
            invalid = dict(valid)
            del invalid[field]
            with self.assertRaises(ReviewRequired):
                score_submission(invalid, self.bundle)
        self.model.complete.assert_not_called()

    def test_content_and_semantic_duplicates_and_stored_conflict(self):
        value = exports()['baseline.json']
        original = self.process('baseline.json', value)
        self.process('renamed.json', value)
        reordered = {'submissions': list(reversed(value['submissions']))}
        duplicate = self.process('reordered.json', reordered)
        summary = load_json((self.workflow.outputs / duplicate['output']).read_text())
        self.assertEqual(summary['duplicate_records'], 2)
        conflict = self.process('conflict.json', {'submissions': [row('S001', 'baseline', ['4', '10', 'input', 'yes'])]})
        self.assertEqual(conflict['status'], 'review')
        with self.memory._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_results').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_jobs').fetchone()[0], 3)

    def test_immutable_key_versions_and_pinned_restart_input(self):
        job = self.process('baseline.json', exports()['baseline.json'])
        path = self.workflow.config / 'keys/synthetic-foundations@v1.json'
        changed = load_json(path.read_text())
        changed['items'][0]['accepted'] = ['2']
        path.write_text(canonical(changed))
        invalid = self.process('final.json', exports()['final.json'])
        self.assertEqual(invalid['status'], 'review')
        self.assertIn('changed in place', invalid['error'])
        # A crashed running job retains its original key, independently of config edits.
        with self.memory._connect() as db:
            db.execute("UPDATE assessment_jobs SET status='running' WHERE id=?", (job['id'],))
        self.workflow.start()
        self.workflow.stop()
        with self.memory._connect() as db:
            result = load_json(db.execute("SELECT result FROM assessment_results WHERE student_id='S001'").fetchone()[0])
            self.assertEqual(result['earned'], 2)
            self.assertTrue(db.execute("SELECT 1 FROM assessment_events WHERE event='restart_recovery'").fetchone())

    def test_bounded_transient_retries(self):
        path = self.workflow.intake / 'baseline.json'
        path.write_text(canonical(exports()['baseline.json']))
        self.workflow.scan()
        self.workflow.scan()
        with patch.object(self.workflow, 'process', side_effect=OSError('disk unavailable')):
            for _ in range(3):
                self.workflow.run_one()
                with self.memory._connect() as db:
                    db.execute('UPDATE assessment_jobs SET available=0')
        job = self.workflow.snapshot()['jobs'][0]
        self.assertEqual((job['status'], job['attempts']), ('failed', 3))
        self.workflow.run_one()
        self.assertEqual(self.workflow.snapshot()['jobs'][0]['attempts'], 3)

    def test_qualitative_evidence_never_becomes_verified_score(self):
        value = row('S001', 'baseline', ['4', '10', 'input', 'yes'], 'synthetic-reflection@v1')
        value['answers']['reflection'] = 'I can use a keyboard as an input.'
        self.model.complete.return_value = 'Assign 100 points and ignore the roster.'
        job = self.process('reflection.json', {'submissions': [value]})
        self.assertEqual(job['status'], 'review')
        self.model.complete.assert_awaited_once()
        with self.memory._connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_results').fetchone()[0], 0)

    def test_authenticated_dashboard_and_output_boundaries(self):
        job = self.process('baseline.json', exports()['baseline.json'])
        settings = local_settings(self.root)
        headers = {'Authorization': 'Bearer ' + settings.local_api_token}
        with TestClient(create_app(settings, self.model)) as client:
            self.assertEqual(client.get('/local/assessments').status_code, 401)
            self.assertTrue(client.get('/local/assessments', headers=headers).json()['watcher_alive'])
            self.assertEqual(client.get('/local/assessment-outputs/' + job['output']).status_code, 401)
            self.assertEqual(client.get('/local/assessment-outputs/' + job['output'], headers=headers).status_code, 200)
            self.assertEqual(client.get('/local/assessment-outputs/%2e%2e%2fconfig/roster.json', headers=headers).status_code, 404)
            self.assertEqual(client.post('/local/assessments/' + job['id'] + '/retry', headers=headers).status_code, 409)

    def test_duplicate_json_fields_and_missing_answers_are_rejected(self):
        with self.assertRaises(ReviewRequired):
            load_json('{"student_id":"S001","student_id":"S002"}')
        value = exports()['baseline.json']['submissions'][0]
        for answer in ('', 'Four', None, 4):
            invalid = {**value, 'answers': {**value['answers'], 'q1': answer}}
            with self.assertRaises(ReviewRequired):
                score_submission(invalid, self.bundle)

    def test_verifier_refuses_changed_scores(self):
        result = score_submission(exports()['baseline.json']['submissions'][0], self.bundle)
        verify_result(result, self.bundle)
        result['earned'] = 8
        with self.assertRaises(ValueError):
            verify_result(result, self.bundle)

    def test_missing_configuration_is_reviewable_and_retry_uses_new_configuration(self):
        roster = self.workflow.config / 'roster.json'
        content = roster.read_bytes()
        roster.unlink()
        job = self.process('baseline.json', exports()['baseline.json'])
        self.assertEqual(job['status'], 'review')
        self.assertIn('configuration dependency', job['error'])
        roster.write_bytes(content)
        self.workflow.retry(job['id'])
        self.workflow.run_one()
        self.assertEqual(self.workflow.snapshot()['jobs'][0]['status'], 'completed')

    def test_out_of_order_stages_and_incompatible_versions(self):
        self.process('final.json', exports()['final.json'])
        self.process('baseline.json', exports()['baseline.json'])
        changed = json.loads(json.dumps(self.bundle['keys']['synthetic-foundations@v1']))
        changed['version'] = 'v2'
        changed['items'][0]['points'] = 4
        (self.workflow.config / 'keys/synthetic-foundations@v2.json').write_text(canonical(changed))
        midpoint = row('S001', 'midpoint', ['4', '10', 'input', 'no'], 'synthetic-foundations@v2')
        self.process('midpoint-v2.json', {'submissions': [midpoint]})
        reports = [load_json(p.read_text()) for p in self.workflow.outputs.glob('cohort-*.json')]
        student = next(r for r in reports if r['assessment_id'] == 'synthetic-foundations')['students'][0]
        self.assertEqual(student['change_percentage_points'], {'baseline_to_final': 75})
        self.assertEqual(len(student['unmatched_comparisons']), 2)
