"""Actual-machine synthetic acceptance. Never polls Telegram or invokes Azure.

Leaves a poller-free local operator running only with --leave-running. Private
configuration, PID, logs, restored state and results remain under data/.
"""
import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.backup_local import backup
from scripts.restore_local import restore

ROOT = Path(__file__).resolve().parents[1]


def validate(model, port, leave_running, state_root=None, install=False):
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    state_root = Path(state_root).resolve() if state_root else ROOT / 'data'
    if install and ((state_root / 'state').exists() or (state_root / '.env.local').exists()):
        raise FileExistsError('Permanent state/config already exists; installation never overwrites it')
    evidence = state_root / ('acceptance-' + stamp)
    evidence.mkdir(parents=True)
    data = evidence / 'original'
    token = secrets.token_urlsafe(36)
    headers = {'Authorization': 'Bearer ' + token}
    base_url = f'http://127.0.0.1:{port}'
    config = evidence / '.env.local'
    chat_id = 999000111
    log = (evidence / 'runtime.log').open('ab')
    process = None
    results = {'observed_at': datetime.now(UTC).isoformat(), 'model': model,
               'synthetic_only': True, 'telegram_polled': False, 'checks': [], 'running': False}

    def record(check):
        results['checks'].append(check)
        print(json.dumps({'passed': check}), flush=True)

    def start(storage, endpoint='http://127.0.0.1:11434'):
        nonlocal process
        config.write_text('\n'.join([
            'NEXUS_TELEGRAM_ENABLED=false', 'BOT_ALLOWED_CHAT_IDS=' + str(chat_id),
            'NEXUS_LOCAL_API_TOKEN=' + token, 'OLLAMA_MODEL=' + model,
            'OLLAMA_BASE_URL=' + endpoint, 'NEXUS_LOCAL_PORT=' + str(port),
            'MODEL_TIMEOUT_SECONDS=180', 'NEXUS_MEMORY_PATH=' + str(storage / 'nexus_memory.sqlite3'),
            'NEXUS_LOCAL_ARTIFACT_PATH=' + str(storage / 'artifacts'),
        ]) + '\n', encoding='utf-8')
        config.chmod(0o600)
        env = {**os.environ, 'NEXUS_LOCAL_ENV_FILE': str(config), 'PYTHONUTF8': '1'}
        process = subprocess.Popen([sys.executable, '-m', 'app.local'], cwd=ROOT, env=env,
            stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (evidence / 'launcher.pid').write_text(str(process.pid), encoding='ascii')
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Local runtime exited; inspect private runtime.log')
            try:
                health = httpx.get(base_url + '/healthz', timeout=1, trust_env=False)
                if health.status_code == 200:
                    assert health.json()['telegram_polling'] is False
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        raise TimeoutError('Local startup did not become healthy')

    def stop():
        nonlocal process
        if process is not None:
            if os.name == 'nt' and process.poll() is None:
                # Windows venv python.exe can be a launcher with a child interpreter.
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, check=True)
            elif process.poll() is None:
                process.terminate()
            process.wait(timeout=20)
            process = None
            try:
                httpx.get(base_url + '/healthz', timeout=1, trust_env=False)
            except httpx.HTTPError:
                pass
            else:
                raise RuntimeError('A server remains on the acceptance port; do not claim a successful restart')

    def command(client, text, allowed_chat=chat_id):
        return client.post('/local/command', json={'chat_id': allowed_chat, 'text': text})

    try:
        with httpx.Client(timeout=180, trust_env=False) as ollama:
            tags = ollama.get('http://127.0.0.1:11434/api/tags')
            tags.raise_for_status()
            if model not in {m['name'] for m in tags.json()['models']}:
                raise ValueError('Choose an installed model; acceptance never downloads one')
        # Do not send a credential to an existing service that happens to occupy our port.
        import socket
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
        start(data)
        record('startup-loopback-poller-disabled')
        with httpx.Client(base_url=base_url, headers=headers, timeout=180, trust_env=False) as client:
            denied = httpx.post(base_url + '/local/command', json={'chat_id': chat_id, 'text': '/find synthetic'}, trust_env=False)
            assert denied.status_code == 401
            assert command(client, '/remember forbidden synthetic', allowed_chat=chat_id + 1).status_code == 403
            record('missing-token-and-unlisted-chat-rejected')
            assert command(client, '/remember synthetic acceptance code ORBIT-724 belongs to the local pilot project').status_code == 200
            assert 'ORBIT-724' in command(client, '/find ORBIT-724').json()['reply']
            record('local-memory-write-and-search')
            brief = command(client, '/brief What is the synthetic acceptance code in memory? Include that exact code.')
            brief.raise_for_status()
            assert 'ORBIT-724' in brief.json()['reply']
            record('actual-ollama-inference-with-retrieved-memory')
            content = b'Synthetic acceptance document: ORBIT-724\nNo personal or production data.\n'
            document = client.put('/local/documents/synthetic-pilot.txt', content=content)
            document.raise_for_status()
            document_id = document.json()['id']
            assert document_id == hashlib.sha256(content).hexdigest()
            assert client.get('/local/documents/' + document_id).content == content
            assert len(client.get('/local/documents?query=synthetic-pilot').json()) == 1
            record('local-attachment-search-and-content-integrity')
            assert 'approval' in command(client, '/draft sign a binding contract').json()['reply']
            assert 'apps.powerapps.com' in command(client, '/cohort desk').json()['reply']
            record('arbiter-approval-and-cohort-desk-links')
        try:
            backup(data, evidence / 'must-not-exist.zip')
        except RuntimeError:
            record('backup-refuses-running-writer')
        else:
            raise AssertionError('Online matched backup was not refused')
        stop()
        start(data)
        with httpx.Client(base_url=base_url, headers=headers, timeout=30, trust_env=False) as client:
            assert 'ORBIT-724' in command(client, '/find ORBIT-724').json()['reply']
            assert client.get('/local/documents/' + document_id).content == content
        record('memory-and-document-survive-process-restart')
        stop()
        manifest = backup(data, evidence / 'pilot-backup.zip')
        restored = evidence / 'restored'
        restored_manifest = restore(evidence / 'pilot-backup.zip', restored)
        assert restored_manifest['counts'] == manifest['counts']
        start(restored)
        with httpx.Client(base_url=base_url, headers=headers, timeout=30, trust_env=False) as client:
            assert 'ORBIT-724' in command(client, '/find ORBIT-724').json()['reply']
            assert client.get('/local/documents/' + document_id).content == content
        record('offline-backup-and-live-restoration-preserve-records-and-document-bytes')
        stop()
        # Real refused loopback connection, without disrupting other Ollama consumers.
        start(restored, endpoint='http://127.0.0.1:1')
        with httpx.Client(base_url=base_url, headers=headers, timeout=30, trust_env=False) as client:
            failed = command(client, '/brief summarize synthetic memory')
            assert failed.status_code == 503 and 'no cloud fallback' in failed.json()['detail']
            assert 'ORBIT-724' in command(client, '/find ORBIT-724').json()['reply']
        record('real-ollama-connection-failure-no-cloud-fallback-memory-still-available')
        stop()
        if install:
            final_data = state_root / 'state'
            restore(evidence / 'pilot-backup.zip', final_data)
            start(final_data)
            stop()
            permanent_config = state_root / '.env.local'
            with permanent_config.open('x', encoding='utf-8') as output:
                output.write(config.read_text(encoding='utf-8'))
            permanent_config.chmod(0o600)
            results['installed_data_directory'] = str(final_data)
            results['installed_env_file'] = str(permanent_config)
        if leave_running:
            start(restored)
            results.update(running=True, pid=process.pid, url=base_url, env_file=str(config),
                           data_directory=str(restored), telegram_polling=False)
            (evidence / 'runtime.pid').write_text(str(process.pid), encoding='ascii')
            process = None  # Deliberately leave only the validated poller-free pilot running.
        results['passed'] = True
        results['backup_counts'] = manifest['counts']
    finally:
        stop()
        log.close()
        (evidence / 'acceptance.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps({'passed': results.get('passed', False), 'checks': len(results['checks']),
                      'running': results['running'], 'evidence': str(evidence)}, indent=2))
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--leave-running', action='store_true')
    parser.add_argument('--state-root', type=Path)
    parser.add_argument('--install', action='store_true', help='Install verified recovered state and private config without overwriting existing state')
    args = parser.parse_args()
    if args.install and args.leave_running:
        parser.error('Use --install then scripts/start_local.ps1 to manage the permanent service')
    validate(args.model, args.port, args.leave_running, args.state_root, args.install)
