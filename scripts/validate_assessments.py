"""Real separate-process, folder-driven synthetic assessment acceptance.

No chat prompts, TestClient, mocked model or mocked worker. The offline repeat
uses a child-interpreter network guard which denies non-loopback sockets/DNS.
Evidence, raw exports, SQLite, reports and process logs are retained locally.
"""
import argparse
import csv
import io
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.assessments import canonical, digest
from scripts.assessment_fixtures import exports, install, row
from scripts.backup_local import backup
from scripts.restore_local import restore


def validate(model, port, state_root=None, leave_running=False, install_state=False):
    evidence = (Path(state_root).resolve() if state_root else ROOT / 'data') / ('assessment-acceptance-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
    evidence.mkdir(parents=True)
    if install_state and ((evidence.parent / 'state').exists() or (evidence.parent / '.env.local').exists()):
        raise FileExistsError('Installation refuses existing state/configuration')
    result = {'synthetic_only': True, 'started_at': datetime.now(UTC).isoformat(),
              'model': model, 'checks': [], 'cloud_calls': False, 'chat_prompts': 0,
              'network_boundary': 'Offline runtime Python process blocks non-loopback sockets and DNS; host firewall unchanged'}
    process = None
    process_job = None
    log = None
    current_data = None
    config = None
    token = secrets.token_urlsafe(36)
    base_url = f'http://127.0.0.1:{port}'
    headers = {'Authorization': 'Bearer ' + token}

    def record(check, **details):
        result['checks'].append({'check': check, **details})
        (evidence / 'acceptance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({'passed': check, **details}), flush=True)

    def get(path):
        response = httpx.get(base_url + path, headers=headers, timeout=10, trust_env=False)
        response.raise_for_status()
        return response.json()

    def sql(query, args=()):
        with closing(sqlite3.connect(current_data / 'nexus_memory.sqlite3', timeout=10)) as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute(query, args)]

    def start(data, offline, model_endpoint='http://127.0.0.1:11434'):
        nonlocal process, process_job, log, config, current_data
        current_data = data
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', port))
        config = data.parent / '.env.local'
        config.write_text('\n'.join([
            'NEXUS_TELEGRAM_ENABLED=false', 'BOT_ALLOWED_CHAT_IDS=999000111',
            'NEXUS_LOCAL_API_TOKEN=' + token, 'OLLAMA_MODEL=' + model,
            'OLLAMA_BASE_URL=' + model_endpoint, 'NEXUS_LOCAL_PORT=' + str(port),
            'MODEL_TIMEOUT_SECONDS=40', 'NEXUS_MEMORY_PATH=' + str(data / 'nexus_memory.sqlite3'),
            'NEXUS_LOCAL_ARTIFACT_PATH=' + str(data / 'artifacts'),
        ]) + '\n', encoding='utf-8')
        env = {**os.environ, 'NEXUS_LOCAL_ENV_FILE': str(config), 'PYTHONUTF8': '1'}
        if offline:
            env['PYTHONPATH'] = str(ROOT / 'scripts/assessment_offline_guard')
            env['NEXUS_OFFLINE_EVIDENCE'] = str(data.parent / 'network-guard.jsonl')
        log = (data.parent / 'runtime.log').open('ab')
        process = subprocess.Popen([sys.executable, '-m', 'app.local'], cwd=ROOT, env=env,
                                   stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if os.name == 'nt':
            # Own the launched tree directly. taskkill /T depends on process
            # enumeration services unavailable in some managed Windows sessions.
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
            kernel.CreateJobObjectW.restype = wintypes.HANDLE
            kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            kernel.AssignProcessToJobObject.restype = wintypes.BOOL
            kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel.TerminateJobObject.restype = wintypes.BOOL
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
            handle = kernel.CreateJobObjectW(None, None)
            if not handle or not kernel.AssignProcessToJobObject(handle, int(process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            process_job = (kernel, handle)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Runtime exited; inspect ' + str(data.parent / 'runtime.log'))
            try:
                health = httpx.get(base_url + '/healthz', timeout=1, trust_env=False)
                if health.status_code == 200:
                    assert health.json()['telegram_polling'] is False
                    assert health.json()['paid_cloud'] == 'disabled'
                    snapshot = get('/local/assessments')
                    assert snapshot['watcher_alive']
                    return
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        raise TimeoutError('Runtime startup timed out')

    def stop():
        nonlocal process, process_job, log
        if process is not None:
            if process.poll() is None:
                if os.name == 'nt':
                    import ctypes
                    kernel, handle = process_job
                    if not kernel.TerminateJobObject(handle, 1):
                        raise ctypes.WinError(ctypes.get_last_error())
                else:
                    process.kill()
            process.wait(timeout=20)
            process = None
        if process_job:
            kernel, handle = process_job
            kernel.CloseHandle(handle)
            process_job = None
        if log:
            log.close()
            log = None
        try:
            httpx.get(base_url + '/healthz', timeout=.5, trust_env=False)
        except httpx.HTTPError:
            return
        raise AssertionError('Process still serves acceptance port after shutdown')

    def drop(name, content):
        intake = current_data / 'artifacts/assessments/intake'
        raw = content if isinstance(content, bytes) else canonical(content).encode()
        temporary = intake / (name + '.part')
        temporary.write_bytes(raw)
        temporary.rename(intake / name)
        return digest(raw)

    def wait_job(job_id, statuses=('completed', 'review', 'failed'), timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            jobs = sql('SELECT * FROM assessment_jobs WHERE id=?', (job_id,))
            if jobs and jobs[0]['status'] in statuses:
                return jobs[0]
            time.sleep(.1)
        raise TimeoutError('Job not terminal: ' + job_id)

    def output(job):
        path = '/local/assessment-outputs/' + job['output']
        value = get(path)
        assert value['job_id'] == job['id']
        return value

    def verify_report():
        snapshot = get('/local/assessments')
        reports = [get('/local/assessment-outputs/' + name) for name in snapshot['reports'] if name.endswith('.json')]
        report = next(r for r in reports if r['assessment_id'] == 'synthetic-foundations')
        assert report['enrolled'] == 3
        assert report['stages']['baseline']['mean_percent'] == 50
        assert report['stages']['midpoint']['mean_percent'] == 75
        assert report['stages']['final']['mean_percent'] == 87.5
        assert report['stages']['baseline']['missing_student_ids'] == ['S003']
        assert report['stages']['midpoint']['missing_student_ids'] == ['S002', 'S003']
        assert report['stages']['final']['missing_student_ids'] == ['S003']
        assert report['stages']['baseline']['skills']['numeracy']['earned'] == 6
        assert report['stages']['baseline']['skills']['numeracy']['possible'] == 8
        by_id = {student['student_id']: student for student in report['students']}
        assert by_id['S001']['change_percentage_points'] == {'baseline_to_midpoint': 50, 'midpoint_to_final': 25, 'baseline_to_final': 75}
        assert by_id['S002']['change_percentage_points']['baseline_to_final'] == 0
        assert by_id['S002']['recommended_foundation_work'] == ['Practice counting in pairs to ten.']
        assert by_id['S003']['scores'] == {}
        assert len(sql('SELECT * FROM assessment_results')) == 5
        return report

    try:
        # Require an already installed model; no download and no paid fallback.
        tags = httpx.get('http://127.0.0.1:11434/api/tags', timeout=3, trust_env=False)
        tags.raise_for_status()
        assert model in {m['name'] for m in tags.json()['models']}
        for mode in ('online', 'offline'):
            data = evidence / mode / 'state'
            root = data / 'artifacts/assessments'
            install(root)
            start(data, mode == 'offline')
            for name, content in exports().items():
                job = wait_job(drop(name, content))
                assert job['status'] == 'completed', job['error']
                summary = output(job)
                assert summary['issues'] == []
                for report in summary['reports']:
                    response = httpx.get(base_url + '/local/assessment-outputs/' + report, headers=headers, trust_env=False)
                    assert response.status_code == 200 and response.content
            report = verify_report()
            (data.parent / 'verified-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            record(mode + ':autonomous-drops-and-independent-report-accuracy', scores={'S001': [25, 75, 100], 'S002': [75, None, 75]},
                   means=[50, 75, 87.5], missing_final=['S003'], matched_gain_S001=75)

            before = len(sql('SELECT * FROM assessment_jobs'))
            drop('renamed-baseline.json', exports()['baseline.json'])
            deadline = time.monotonic() + 10
            while not sql("SELECT * FROM assessment_events WHERE event='duplicate_file'") and time.monotonic() < deadline:
                time.sleep(.1)
            assert len(sql('SELECT * FROM assessment_jobs')) == before
            assert sql("SELECT * FROM assessment_events WHERE event='duplicate_file'")
            semantic = {'submissions': list(reversed(exports()['baseline.json']['submissions']))}
            duplicate = wait_job(drop('reordered-baseline.json', semantic))
            assert output(duplicate)['duplicate_records'] == 2
            stream = io.StringIO(newline='')
            writer = csv.DictWriter(stream, fieldnames=['student_id', 'cohort', 'stage', 'answer_key', 'q1', 'q2', 'q3', 'q4'])
            writer.writeheader()
            for submission in exports()['baseline.json']['submissions']:
                writer.writerow({**{k: v for k, v in submission.items() if k != 'answers'}, **submission['answers']})
            duplicate = wait_job(drop('baseline.csv', stream.getvalue().encode()))
            assert output(duplicate)['duplicate_records'] == 2
            verify_report()
            record(mode + ':hash-renamed-and-semantic-json-csv-duplicates-prevented', unique_results=5)

            malformed = wait_job(drop('malformed.json', b'{"submissions": ['))
            assert malformed['status'] == 'failed' and malformed['attempts'] == 1
            assert 'Malformed' in output(malformed)['issues'][0]['issue']
            invalid = row('S999', 'baseline', ['4', '10', 'input', 'yes'])
            missing = row('S001', 'baseline', ['4', '10', 'input', 'yes'])
            missing['answers'].pop('q2')
            review = wait_job(drop('invalid-records.json', {'submissions': [invalid, missing]}))
            assert review['status'] == 'review' and len(output(review)['issues']) == 2
            conflict = wait_job(drop('conflict.json', {'submissions': [row('S001', 'baseline', ['4', '10', 'input', 'yes'])]}))
            assert conflict['status'] == 'review'
            verify_report()
            record(mode + ':malformed-missing-unmatched-and-conflicting-records-withheld', unique_results=5)

            reflection = row('S001', 'baseline', ['4', '10', 'input', 'yes'], 'synthetic-reflection@v1')
            reflection['answers']['reflection'] = 'I know the keyboard is an input but need help explaining sensor inputs.'
            qualitative = wait_job(drop('reflection.json', {'submissions': [reflection]}))
            issue = output(qualitative)['issues'][0]
            assert qualitative['status'] == 'review' and issue['model_suggestion_verified'] is False
            assert issue.get('local_model_suggestion'), issue
            assert len(sql('SELECT * FROM assessment_results')) == 5
            record(mode + ':actual-local-ollama-interpretation-preserved-for-staff-review', verified_scores_from_model=0)
            if mode == 'offline':
                guards = [json.loads(line) for line in (data.parent / 'network-guard.jsonl').read_text().splitlines()]
                assert any(g['event'] == 'guard_verified:tcp' for g in guards)
                assert any(g['event'] == 'guard_verified:dns' for g in guards)
                record('offline:runtime-network-denial-proven', tcp_and_dns_blocked=True)

                # Crash a real running job after its first committed result, then replay.
                recover_row = row('S003', 'baseline', ['4', '10', 'input', 'yes'])
                recovery_id = drop('restart-recovery.json', {'submissions': [recover_row] * 6000})
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    running = sql("SELECT * FROM assessment_jobs WHERE id=? AND status='running'", (recovery_id,))
                    committed = sql("SELECT * FROM assessment_results WHERE student_id='S003' AND stage='baseline'")
                    if running and committed:
                        stop()
                        break
                    time.sleep(.01)
                else:
                    raise AssertionError('Could not observe a partially committed running job for crash drill')
                assert sql('SELECT status FROM assessment_jobs WHERE id=?', (recovery_id,))[0]['status'] == 'running'
                start(data, True)
                recovered = wait_job(recovery_id, timeout=120)
                assert recovered['status'] == 'completed' and recovered['attempts'] == 2
                assert len(sql('SELECT * FROM assessment_results')) == 6
                assert sql("SELECT * FROM assessment_events WHERE job_id=? AND event='restart_recovery'", (recovery_id,))
                output(recovered)
                record('offline:process-killed-during-running-job-recovered-on-restart', attempts=2, unique_results=6)

                # Real filesystem failure: a directory occupies the atomic-output temp file.
                retry_content = {'submissions': [row('S003', 'final', ['4', '10', 'input', 'yes'])]}
                retry_id = digest(canonical(retry_content).encode())
                blocker = root / 'outputs' / retry_id / 'job.json.tmp'
                blocker.mkdir(parents=True)
                failed = wait_job(drop('bounded-retry.json', retry_content), timeout=60)
                assert failed['status'] == 'failed' and failed['attempts'] == 3
                time.sleep(3)
                assert sql('SELECT attempts FROM assessment_jobs WHERE id=?', (retry_id,))[0]['attempts'] == 3
                blocker.rmdir()
                response = httpx.post(base_url + '/local/assessments/' + retry_id + '/retry', headers=headers, trust_env=False)
                response.raise_for_status()
                repaired = wait_job(retry_id)
                assert repaired['status'] == 'completed' and len(sql('SELECT * FROM assessment_results')) == 7
                record('offline:real-disk-error-retries-bounded-and-explicit-retry-idempotent', automatic_attempts=3, unique_results=7)

                # Objective processing must continue even with a genuinely refused model endpoint.
                stop()
                start(data, True, model_endpoint='http://127.0.0.1:1')
                no_model = wait_job(drop('objective-without-model.json', {'submissions': [row('S003', 'midpoint', ['4', '10', 'input', 'yes'])]}))
                assert no_model['status'] == 'completed'
                record('offline:objective-work-completes-with-local-model-unavailable', unique_results=8)
            stop()

        data = evidence / 'offline/state'
        manifest = backup(data, evidence / 'assessments-backup.zip')
        restored = evidence.parent / 'state' if install_state else evidence / 'restored/state'
        restore(evidence / 'assessments-backup.zip', restored)
        start(restored, True)
        assert len(sql('SELECT * FROM assessment_results')) == 8
        assert sql('PRAGMA integrity_check')[0]['integrity_check'] == 'ok'
        assert get('/local/assessments')['watcher_alive']
        record('offline:checksummed-backup-and-live-restoration', counts=manifest['counts'])
        result['passed'] = True
        result['intake'] = str((restored / 'artifacts/assessments/intake').resolve())
        result['outputs'] = str((restored / 'artifacts/assessments/outputs').resolve())
        result['url'] = base_url
        result['configuration_file'] = str(config)
        if leave_running:
            result['running'] = True
            result['launcher_pid'] = process.pid
            result['server_pid'] = httpx.get(base_url + '/healthz', trust_env=False).json()['pid']
            process = None
        else:
            stop()
            result['running'] = False
    except Exception as error:
        result['passed'] = False
        result['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        if process is not None:
            stop()
        if log:
            log.close()
        result['finished_at'] = datetime.now(UTC).isoformat()
        (evidence / 'acceptance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({'evidence': str(evidence), 'passed': result.get('passed', False), 'running': result.get('running', False)}), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--port', type=int, default=8876)
    parser.add_argument('--state-root', type=Path)
    parser.add_argument('--leave-running', action='store_true')
    parser.add_argument('--install', action='store_true', help='Restore validated synthetic state to state-root/state; refuses existing state/config')
    args = parser.parse_args()
    validate(args.model, args.port, args.state_root, args.leave_running, args.install)
