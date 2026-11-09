"""Local assessment tools and durable, single-writer folder workflow.

All scores come from pinned keys. Model output is review evidence only. The
runtime's OS lease owns this worker; SQLite and content-addressed files recover
at-least-once execution into exactly-once student results.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import html
import io
import json
import logging
import os
import re
import sqlite3
import threading
import time
from collections import Counter
from pathlib import Path

from app.agents import AssessmentInterpretationAgent
from app.document_flow import summarize_document_flow
from app.intake import build_student_intake_record
from app.memory import MemoryStore, utc_now

LOG = logging.getLogger(__name__)
STAGES = ('baseline', 'midpoint', 'final')
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z')
MAX_BYTES = 5 * 1024 * 1024
MAX_ATTEMPTS = 3


class ReviewRequired(ValueError):
    pass


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def load_json(content):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ReviewRequired(f'Duplicate JSON field: {key}')
            result[key] = value
        return result
    return json.loads(content, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ReviewRequired('Non-finite JSON number')))


def atomic_bytes(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('wb') as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value):
    atomic_bytes(path, json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False).encode('utf-8'))


def identifier(value, field):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ReviewRequired(f'{field} must be an explicit ID (letters, digits, dot, dash or underscore)')
    return value


def validate_configuration(roster, keys):
    if not isinstance(roster, dict) or set(roster) != {'students'} or not isinstance(roster['students'], list):
        raise ReviewRequired('Roster requires a students array')
    members = set()
    for student in roster['students']:
        if not isinstance(student, dict) or set(student) != {'student_id', 'cohort'}:
            raise ReviewRequired('Roster students require only student_id and cohort')
        member = (identifier(student['student_id'], 'student_id'), identifier(student['cohort'], 'cohort'))
        if member in members:
            raise ReviewRequired('Ambiguous duplicate roster membership')
        members.add(member)
    if not members or not keys:
        raise ReviewRequired('An approved roster and at least one versioned answer key are required')
    for key_id, key in keys.items():
        if not isinstance(key, dict) or set(key) != {'assessment_id', 'version', 'items'}:
            raise ReviewRequired('Answer key requires assessment_id, version and items')
        expected = identifier(key['assessment_id'], 'assessment_id') + '@' + identifier(key['version'], 'version')
        if key_id != expected or not isinstance(key['items'], list) or not key['items']:
            raise ReviewRequired('Answer-key filename must be assessment_id@version.json with nonempty items')
        ids = set()
        objective = 0
        for item in key['items']:
            if not isinstance(item, dict) or set(item) != {'id', 'kind', 'accepted', 'choices', 'points', 'skill', 'foundation'}:
                raise ReviewRequired('Key items require id, kind, accepted, choices, points, skill and foundation')
            qid = identifier(item['id'], 'question id')
            if qid in ids:
                raise ReviewRequired('Duplicate question ID in key')
            ids.add(qid)
            if item['kind'] not in {'objective', 'interpretation'}:
                raise ReviewRequired('Unknown question kind')
            for field in ('accepted', 'choices'):
                if not isinstance(item[field], list) or any(not isinstance(x, str) or not x for x in item[field]):
                    raise ReviewRequired(f'{field} must be an array of nonempty strings')
                if len(set(item[field])) != len(item[field]):
                    raise ReviewRequired(f'Duplicate {field} in key')
            if any(not isinstance(item[f], str) or not item[f].strip() for f in ('skill', 'foundation')):
                raise ReviewRequired('Every item requires a skill and approved foundation recommendation')
            if (type(item['points']) is not int or not 0 <= item['points'] <= 10000):
                raise ReviewRequired('Points must be bounded nonnegative integers')
            if item['kind'] == 'objective':
                objective += item['points']
                if item['points'] == 0 or not item['accepted'] or not set(item['accepted']) <= set(item['choices']):
                    raise ReviewRequired('Objective items need positive points and accepted answers within choices')
            elif item['points'] != 0 or item['accepted'] or item['choices']:
                raise ReviewRequired('Interpretation items must have zero points and empty accepted/choices; staff review is required')
        if not objective:
            raise ReviewRequired('A key must contain objective scoring items')
    return members


def parse_submissions(content: bytes, suffix: str):
    text = content.decode('utf-8-sig')
    if suffix == '.json':
        value = load_json(text)
        if not isinstance(value, dict) or set(value) != {'submissions'} or not isinstance(value['submissions'], list):
            raise ReviewRequired('JSON requires exactly a submissions array')
        rows = value['submissions']
    elif suffix == '.csv':
        reader = csv.DictReader(io.StringIO(text, newline=''))
        fields = reader.fieldnames or []
        if len(set(fields)) != len(fields) or not {'student_id', 'cohort', 'stage', 'answer_key'} <= set(fields):
            raise ReviewRequired('CSV needs unique headers: student_id, cohort, stage, answer_key and question IDs')
        rows = []
        for record in reader:
            if None in record or any(value is None for value in record.values()):
                raise ReviewRequired('CSV has extra or missing columns')
            row = {name: record.pop(name) for name in ('student_id', 'cohort', 'stage', 'answer_key')}
            row['answers'] = record
            rows.append(row)
    else:
        raise ReviewRequired('Unsupported file type; export canonical UTF-8 JSON or CSV')
    if not rows or len(rows) > 10000:
        raise ReviewRequired('Submission count must be between 1 and 10000')
    return rows


def score_submission(row, bundle):
    if not isinstance(row, dict) or set(row) != {'student_id', 'cohort', 'stage', 'answer_key', 'answers'}:
        raise ReviewRequired('Required fields: student_id, cohort, stage, answer_key, answers; unknown fields require mapping')
    sid = identifier(row['student_id'], 'student_id')
    cohort = identifier(row['cohort'], 'cohort')
    if (sid, cohort) not in {(s['student_id'], s['cohort']) for s in bundle['roster']['students']}:
        raise ReviewRequired('Student ID/cohort does not match the approved roster')
    if row['stage'] not in STAGES:
        raise ReviewRequired('stage must be baseline, midpoint or final')
    if not isinstance(row['answer_key'], str) or row['answer_key'] not in bundle['keys']:
        raise ReviewRequired('Explicit versioned answer key not found')
    key = bundle['keys'][row['answer_key']]
    answers = row['answers']
    if not isinstance(answers, dict) or set(answers) != {q['id'] for q in key['items']}:
        raise ReviewRequired('Missing or unknown question fields')
    details = []
    interpretations = []
    for item in key['items']:
        answer = answers[item['id']]
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 8000:
            raise ReviewRequired(f"{item['id']}: explicit nonempty text answer required (max 8000 characters)")
        if item['kind'] == 'interpretation':
            interpretations.append({'question': item['id'], 'response': answer, 'foundation': item['foundation']})
            continue
        # Exact key values only: aliases belong in the versioned key, never in an LLM.
        if answer not in item['choices']:
            raise ReviewRequired(f"{item['id']}: answer outside approved choices; interpretation required")
        earned = item['points'] if answer in item['accepted'] else 0
        details.append({'question': item['id'], 'skill': item['skill'], 'earned': earned,
                        'possible': item['points'], 'foundation': item['foundation']})
    earned = sum(item['earned'] for item in details)
    possible = sum(item['possible'] for item in details)
    return {**row, 'assessment_id': key['assessment_id'], 'key_sha256': digest(canonical(key).encode()),
            'earned': earned, 'possible': possible, 'percent': round(100 * earned / possible, 2),
            'details': details, 'interpretations': interpretations}


def verify_result(result, bundle):
    """Verify the score and per-question evidence against the pinned key."""
    key = bundle['keys'][result['answer_key']]
    objective = [q for q in key['items'] if q['kind'] == 'objective']
    expected = {q['id']: (q['points'] if result['answers'][q['id']] in q['accepted'] else 0, q['points']) for q in objective}
    actual = {d['question']: (d['earned'], d['possible']) for d in result['details']}
    earned, possible = sum(v[0] for v in expected.values()), sum(v[1] for v in expected.values())
    if (len(result['details']) != len(expected) or actual != expected or
            (result['earned'], result['possible'], result['percent']) != (earned, possible, round(100 * earned / possible, 2)) or
            result['key_sha256'] != digest(canonical(key).encode())):
        raise ValueError('Deterministic score verification failed')


class AssessmentWorkflow:
    def __init__(self, memory: MemoryStore, artifacts: Path, model):
        self.memory, self.model = memory, model
        self.root = Path(artifacts) / 'assessments'
        self.intake = self.root / 'intake'
        self.config = self.root / 'config'
        self.outputs = self.root / 'outputs'
        for path in (self.intake, self.config / 'keys', self.outputs, self.root / 'sources'):
            path.mkdir(parents=True, exist_ok=True)
        self.stop_event = threading.Event()
        self.thread = None
        self.seen = {}
        self.last_error = None
        self._init_db()

    def _init_db(self):
        with self.memory._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS assessment_jobs (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, suffix TEXT NOT NULL,
                    status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                    available REAL NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL,
                    error TEXT, bundle TEXT, output TEXT);
                CREATE TABLE IF NOT EXISTS assessment_results (
                    cohort TEXT NOT NULL, student_id TEXT NOT NULL, stage TEXT NOT NULL,
                    assessment_id TEXT NOT NULL, answer_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    job_id TEXT NOT NULL, result TEXT NOT NULL,
                    PRIMARY KEY(cohort, student_id, stage, assessment_id));
                CREATE TABLE IF NOT EXISTS assessment_keys (id TEXT PRIMARY KEY, sha256 TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS assessment_events (
                    id INTEGER PRIMARY KEY, job_id TEXT, at TEXT NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL);
            ''')

    def event(self, db, job_id, event, detail=''):
        db.execute('INSERT INTO assessment_events(job_id,at,event,detail) VALUES(?,?,?,?)',
                   (job_id, utc_now(), event, detail))

    def configuration(self):
        try:
            roster = load_json((self.config / 'roster.json').read_text(encoding='utf-8-sig'))
            keys = {path.stem: load_json(path.read_text(encoding='utf-8-sig'))
                    for path in sorted((self.config / 'keys').glob('*.json'))}
            validate_configuration(roster, keys)
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise ReviewRequired('Assessment configuration dependency: ' + str(error)) from None
        return {'roster': roster, 'keys': keys}

    def start(self):
        # Called only while the existing runtime FileLease is held.
        with self.memory._connect() as db:
            for job in db.execute("SELECT * FROM assessment_jobs WHERE status='running'").fetchall():
                status = 'pending' if job['attempts'] < MAX_ATTEMPTS else 'failed'
                db.execute('UPDATE assessment_jobs SET status=?,available=0,updated=?,error=? WHERE id=?',
                           (status, utc_now(), 'Interrupted execution recovered after restart', job['id']))
                self.event(db, job['id'], 'restart_recovery', status)
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, name='nexus-assessments', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join()  # Finish the current bounded local operation before releasing the runtime lease.

    def run(self):
        while not self.stop_event.is_set():
            try:
                self.scan()
                self.run_one()
                self.last_error = None
            except Exception as error:
                LOG.exception('Assessment watcher iteration failed')
                self.last_error = type(error).__name__ + ': ' + str(error)
            self.stop_event.wait(1)

    def scan(self):
        present = set()
        for path in sorted(self.intake.iterdir()):
            if not path.is_file() or path.is_symlink() or path.name.startswith('.') or path.suffix.lower() in {'.tmp', '.part'}:
                continue
            present.add(path)
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            previous = self.seen.get(path)
            if previous != (signature, True):
                if previous == (signature, False):
                    if stat.st_size > MAX_BYTES:
                        content = canonical({'oversize_file': path.name, 'signature': signature}).encode()
                    else:
                        content = path.read_bytes()
                        if signature != (path.stat().st_size, path.stat().st_mtime_ns):
                            continue
                    job_id = digest(content)
                    source = self.root / 'sources' / (job_id + '.blob')
                    if not source.exists():
                        temporary = source.with_suffix('.tmp')
                        with temporary.open('wb') as output:
                            output.write(content)
                            output.flush()
                            os.fsync(output.fileno())
                        os.replace(temporary, source)
                    with self.memory._connect() as db:
                        cursor = db.execute('''INSERT OR IGNORE INTO assessment_jobs
                            (id,name,suffix,status,created,updated,error) VALUES(?,?,?,?,?,?,?)''',
                            (job_id, path.name, path.suffix.lower(), 'pending', utc_now(), utc_now(),
                             'File exceeds 5 MiB; split export before resubmitting' if stat.st_size > MAX_BYTES else None))
                        self.event(db, job_id, 'enqueued' if cursor.rowcount else 'duplicate_file', path.name)
                    self.seen[path] = (signature, True)
                else:
                    self.seen[path] = (signature, False)
        self.seen = {path: value for path, value in self.seen.items() if path in present}

    def claim(self):
        with self.memory._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = db.execute("SELECT * FROM assessment_jobs WHERE status='pending' AND available<=? ORDER BY created,id LIMIT 1",
                             (time.time(),)).fetchone()
            if job is None:
                return None
            db.execute("UPDATE assessment_jobs SET status='running',attempts=attempts+1,updated=? WHERE id=?", (utc_now(), job['id']))
            self.event(db, job['id'], 'running', str(job['attempts'] + 1))
            return dict(db.execute('SELECT * FROM assessment_jobs WHERE id=?', (job['id'],)).fetchone())

    def run_one(self):
        job = self.claim()
        if job is None:
            return
        try:
            self.process(job)
        except Exception as error:
            message = type(error).__name__ + ': ' + str(error)
            retryable = isinstance(error, (OSError, sqlite3.OperationalError))
            status = 'pending' if retryable and job['attempts'] < MAX_ATTEMPTS else 'failed'
            summary = {'job_id': job['id'], 'status': status, 'issues': [{'row': None, 'issue': message}]}
            try:
                atomic_json(self.outputs / job['id'] / 'job.json', summary)
            except OSError:
                pass
            with self.memory._connect() as db:
                db.execute('UPDATE assessment_jobs SET status=?,available=?,updated=?,error=?,output=? WHERE id=?',
                           (status, time.time() + min(30, 2 ** job['attempts']), utc_now(), message,
                            job['id'] + '/job.json' if (self.outputs / job['id'] / 'job.json').exists() else None, job['id']))
                self.event(db, job['id'], status, message)

    def pin_bundle(self, job):
        if job['bundle']:
            return load_json(job['bundle'])
        bundle = self.configuration()
        with self.memory._connect() as db:
            for key_id, key in bundle['keys'].items():
                sha = digest(canonical(key).encode())
                previous = db.execute('SELECT sha256 FROM assessment_keys WHERE id=?', (key_id,)).fetchone()
                if previous and previous[0] != sha:
                    raise ReviewRequired(f'Answer key {key_id} was changed in place; publish a new version')
                db.execute('INSERT OR IGNORE INTO assessment_keys VALUES(?,?)', (key_id, sha))
            db.execute('UPDATE assessment_jobs SET bundle=? WHERE id=?', (canonical(bundle), job['id']))
        return bundle

    def process(self, job):
        content = (self.root / 'sources' / (job['id'] + '.blob')).read_bytes()
        if digest(content) != job['id']:
            raise ValueError('Archived source checksum failed')
        if job['error'] and job['error'].startswith('File exceeds'):
            raise ValueError(job['error'])
        # Parsing precedes configuration so a broken export is diagnosed even without a key.
        try:
            rows = parse_submissions(content, job['suffix'])
        except (ValueError, UnicodeError, csv.Error, TypeError) as error:
            raise ValueError('Malformed assessment file: ' + str(error)) from None
        issues, accepted, duplicates = [], [], 0
        try:
            bundle = self.pin_bundle(job)
        except ReviewRequired as error:
            self.finish(job, 'review', [], [{'row': None, 'issue': str(error)}], 0)
            return
        scored = []
        for index, row in enumerate(rows, 1):
            try:
                result = score_submission(row, bundle)
                verify_result(result, bundle)
                scored.append((index, result))
            except (ReviewRequired, TypeError) as error:
                issues.append({'row': index, 'issue': str(error)})
        # Conflicting rows within one export are all withheld, never selected by order.
        identities = Counter((r['cohort'], r['student_id'], r['stage'], r['assessment_id']) for _, r in scored)
        fingerprints = {}
        for _, result in scored:
            identity = (result['cohort'], result['student_id'], result['stage'], result['assessment_id'])
            fingerprints.setdefault(identity, set()).add(canonical({k: result[k] for k in ('answer_key', 'answers')}))
        for index, result in scored:
            identity = (result['cohort'], result['student_id'], result['stage'], result['assessment_id'])
            if identities[identity] > 1 and len(fingerprints[identity]) > 1:
                issues.append({'row': index, 'issue': 'Conflicting student/stage records within export'})
                continue
            if result['interpretations']:
                issue = {'row': index, 'issue': 'Qualitative response requires staff interpretation; no result committed',
                         'evidence': result['interpretations'], 'model_suggestion_verified': False}
                try:
                    async def suggest():
                        return await asyncio.wait_for(AssessmentInterpretationAgent().interpret(self.model, result['interpretations']), timeout=45)
                    issue['local_model_suggestion'] = asyncio.run(suggest())
                except Exception as error:
                    issue['local_model_error'] = type(error).__name__ + ': ' + str(error)
                issues.append(issue)
                continue
            fingerprint = digest(canonical({k: result[k] for k in ('answer_key', 'answers')}).encode())
            with self.memory._connect() as db:
                previous = db.execute('''SELECT fingerprint,job_id FROM assessment_results
                    WHERE cohort=? AND student_id=? AND stage=? AND assessment_id=?''', identity).fetchone()
                if previous:
                    if previous['fingerprint'] != fingerprint:
                        issues.append({'row': index, 'issue': 'Conflicts with stored student/stage result; staff reconciliation required',
                                       'existing_job': previous['job_id']})
                        continue
                    duplicates += 1
                else:
                    result['intake'] = summarize_document_flow(build_student_intake_record(result['student_id'], [job['id'] + '.blob'], 'artifacts/assessments/sources'))
                    db.execute('INSERT INTO assessment_results VALUES(?,?,?,?,?,?,?,?)',
                               (*identity, result['answer_key'], fingerprint, job['id'], canonical(result)))
                    self.event(db, job['id'], 'result_verified', canonical({'identity': identity, 'earned': result['earned'], 'possible': result['possible']}))
            accepted.append({'row': index, 'student_id': result['student_id'], 'cohort': result['cohort'],
                             'stage': result['stage'], 'earned': result['earned'], 'possible': result['possible'],
                             'answer_key': result['answer_key'], 'key_sha256': result['key_sha256']})
        # Reports are reproducible projections. A crash before finish replays safely.
        reports = self.build_reports(bundle)
        snapshots = []
        for report in reports:
            target = self.outputs / job['id'] / report
            content = (self.outputs / report).read_bytes()
            atomic_bytes(target, content)
            if target.read_bytes() != content:
                raise ValueError('Saved report verification failed')
            snapshots.append(job['id'] + '/' + report)
        self.finish(job, 'review' if issues else 'completed', accepted, issues, duplicates, snapshots)

    def finish(self, job, status, accepted, issues, duplicates, reports=None):
        summary = {'job_id': job['id'], 'source_name': job['name'], 'source_sha256': job['id'],
                   'status': status, 'verified_results': accepted, 'duplicate_records': duplicates,
                   'issues': issues, 'reports': reports or [], 'finished_at': utc_now()}
        output = job['id'] + '/job.json'
        atomic_json(self.outputs / output, summary)
        # Verify the persisted evidence before marking the durable job terminal.
        if load_json((self.outputs / output).read_text(encoding='utf-8')) != summary:
            raise ValueError('Output verification failed')
        with self.memory._connect() as db:
            db.execute('UPDATE assessment_jobs SET status=?,updated=?,output=?,error=? WHERE id=?',
                       (status, utc_now(), output, canonical(issues) if issues else None, job['id']))
            self.event(db, job['id'], status, f'{len(accepted)} verified rows; {len(issues)} review issues')

    def build_reports(self, bundle):
        with self.memory._connect() as db:
            records = [load_json(row[0]) for row in db.execute('SELECT result FROM assessment_results ORDER BY cohort,student_id,stage')]
        reports = []
        for cohort in sorted({s['cohort'] for s in bundle['roster']['students']}):
            members = sorted(s['student_id'] for s in bundle['roster']['students'] if s['cohort'] == cohort)
            for assessment_id in sorted({k['assessment_id'] for k in bundle['keys'].values()}):
                selected = [r for r in records if r['cohort'] == cohort and r['assessment_id'] == assessment_id]
                students = []
                for sid in members:
                    stages = {r['stage']: r for r in selected if r['student_id'] == sid}
                    changes, unmatched = {}, []
                    for first, second in (('baseline', 'midpoint'), ('midpoint', 'final'), ('baseline', 'final')):
                        if first in stages and second in stages:
                            if stages[first]['key_sha256'] == stages[second]['key_sha256']:
                                changes[first + '_to_' + second] = round(stages[second]['percent'] - stages[first]['percent'], 2)
                            else:
                                unmatched.append(first + '_to_' + second + ': incompatible key versions')
                    latest = next((stages[s] for s in reversed(STAGES) if s in stages), None)
                    gaps = [d for d in latest['details'] if d['earned'] < d['possible']] if latest else []
                    students.append({'student_id': sid, 'scores': {s: {'earned': r['earned'], 'possible': r['possible'],
                        'percent': r['percent'], 'answer_key': r['answer_key']} for s, r in stages.items()},
                        'change_percentage_points': changes, 'unmatched_comparisons': unmatched,
                        'latest_stage': latest['stage'] if latest else None, 'gaps': gaps,
                        'recommended_foundation_work': sorted({d['foundation'] for d in gaps})})
                # Skill aggregates never combine baseline and final observations.
                stage_summaries = {}
                for stage in STAGES:
                    stage_rows = [r for r in selected if r['stage'] == stage and r['student_id'] in members]
                    skills = {}
                    for result in stage_rows:
                        for item in result['details']:
                            skill = skills.setdefault(item['skill'], {'earned': 0, 'possible': 0, 'foundation_work': set()})
                            skill['earned'] += item['earned']
                            skill['possible'] += item['possible']
                            if item['earned'] < item['possible']:
                                skill['foundation_work'].add(item['foundation'])
                    for skill in skills.values():
                        skill['foundation_work'] = sorted(skill['foundation_work'])
                    stage_summaries[stage] = {'submitted': len(stage_rows),
                        'answer_keys': sorted({r['answer_key'] for r in stage_rows}),
                        'mean_percent': round(sum(r['percent'] for r in stage_rows) / len(stage_rows), 2) if stage_rows else None,
                        'missing_student_ids': sorted(set(members) - {r['student_id'] for r in stage_rows}), 'skills': skills}
                report = {'cohort': cohort, 'assessment_id': assessment_id, 'generated_at': utc_now(),
                          'roster_sha256': digest(canonical(bundle['roster']).encode()), 'enrolled': len(members),
                          'missing_definition': 'No verified submission for this stage; this is not a due-date or overdue claim',
                          'stages': stage_summaries, 'students': students,
                          'excluded_historical_student_ids': sorted({r['student_id'] for r in selected} - set(members))}
                name = 'cohort-' + digest((cohort + '/' + assessment_id).encode())[:24]
                atomic_json(self.outputs / (name + '.json'), report)
                # HTML is escaped, self-contained, and suitable for local viewing/printing.
                body = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Cohort assessment report</title>'
                body += '<h1>' + html.escape(cohort + ' / ' + assessment_id) + '</h1>'
                body += '<p>Verified local results. Changes are percentage points. Missing means no verified record, without a due-date claim.</p>'
                body += '<h2>Stage summary and missing submissions</h2><ul>'
                for stage, summary in stage_summaries.items():
                    label = f"{stage}: {summary['submitted']}/{len(members)} submitted; mean {summary['mean_percent']}%; missing: {', '.join(summary['missing_student_ids']) or 'none'}"
                    body += '<li>' + html.escape(label) + '</li>'
                body += '</ul><h2>Student scores, gaps and foundation work</h2><table border="1"><thead><tr><th>Student</th><th>Scores</th><th>Matched changes (pp)</th><th>Latest gaps</th><th>Recommended foundation work</th></tr></thead><tbody>'
                for student in students:
                    scores = '; '.join(f"{stage}: {score['earned']}/{score['possible']} ({score['percent']}%, {score['answer_key']})" for stage, score in student['scores'].items()) or 'No verified submission'
                    changes = '; '.join(f'{pair}: {gain:+g}' for pair, gain in student['change_percentage_points'].items())
                    changes = '; '.join(filter(None, [changes, *student['unmatched_comparisons']])) or 'No matched comparison'
                    gaps = '; '.join(f"{d['skill']} / {d['question']} ({d['earned']}/{d['possible']})" for d in student['gaps'])
                    work = '; '.join(student['recommended_foundation_work'])
                    body += '<tr>' + ''.join('<td>' + html.escape(value) + '</td>' for value in (student['student_id'], scores, changes, gaps or 'No verified gap', work or 'No recommendation from verified answers')) + '</tr>'
                body += '</tbody></table><h2>Evidence and skill totals by stage</h2><pre>' + html.escape(json.dumps(report, indent=2)) + '</pre></html>'
                atomic_bytes(self.outputs / (name + '.html'), body.encode('utf-8'))
                reports.extend([name + '.json', name + '.html'])
        return reports

    def snapshot(self):
        with self.memory._connect() as db:
            counts = {s: 0 for s in ('pending', 'running', 'completed', 'failed', 'review')}
            counts.update({r[0]: r[1] for r in db.execute('SELECT status,COUNT(*) FROM assessment_jobs GROUP BY status')})
            jobs = [dict(r) for r in db.execute('SELECT id,name,status,attempts,created,updated,error,output FROM assessment_jobs ORDER BY created DESC,id LIMIT 200')]
            events = [dict(r) for r in db.execute('SELECT * FROM assessment_events ORDER BY id DESC LIMIT 100')]
        try:
            self.configuration()
            dependency = None
        except ReviewRequired as error:
            dependency = str(error)
        return {'intake': str(self.intake.resolve()), 'outputs': str(self.outputs.resolve()),
                'configuration': str(self.config.resolve()), 'configuration_dependency': dependency,
                'watcher_alive': bool(self.thread and self.thread.is_alive()), 'watcher_error': self.last_error,
                'counts': counts, 'jobs': jobs, 'events': events,
                'reports': sorted(p.name for p in self.outputs.glob('cohort-*') if p.suffix in {'.json', '.html'})}

    def retry(self, job_id):
        with self.memory._connect() as db:
            job = db.execute('SELECT * FROM assessment_jobs WHERE id=?', (job_id,)).fetchone()
            if not job or job['status'] not in {'failed', 'review'}:
                raise ReviewRequired('Only failed or review jobs can be explicitly retried')
            # Explicit staff retry starts a new bounded cycle, and revalidates current configuration.
            db.execute("UPDATE assessment_jobs SET status='pending',attempts=0,available=0,bundle=NULL,updated=?,error=NULL WHERE id=?", (utc_now(), job_id))
            self.event(db, job_id, 'staff_retry', 'Current configuration will be revalidated; stored scores cannot be overwritten')
