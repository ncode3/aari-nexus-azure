import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.cloud_authorization import PaidJobApproval, job_fingerprint
from app.local_api import create_app
from app.local_lock import FileLease
from app.local import configure_local_environment
from app.config import get_settings
from app.memory import MemoryStore
from scripts.backup_local import backup
from scripts.restore_local import restore


def local_settings(root):
    with patch.dict(os.environ, {'OLLAMA_MODEL': 'synthetic-model', 'BOT_ALLOWED_CHAT_IDS': '123',
            'NEXUS_LOCAL_API_TOKEN': 'a' * 48, 'NEXUS_MEMORY_PATH': str(root / 'nexus_memory.sqlite3'),
            'NEXUS_LOCAL_ARTIFACT_PATH': str(root / 'artifacts')}, clear=True), patch('app.local.load_dotenv'):
        configure_local_environment()
        return get_settings()


class LocalAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.settings = local_settings(self.root / 'data')
        self.model = AsyncMock()
        self.model.complete.return_value = 'Synthetic answer from local memory'
        self.headers = {'Authorization': 'Bearer ' + self.settings.local_api_token}

    def command(self, client, text, chat_id=123, headers=None):
        return client.post('/local/command', json={'chat_id': chat_id, 'text': text},
                           headers=self.headers if headers is None else headers)

    def test_auth_origin_host_allowlist_and_no_implicit_poller(self):
        app = create_app(self.settings, self.model)
        with TestClient(app) as client:
            self.assertEqual(self.command(client, '/remember denied', headers={}).status_code, 401)
            self.assertEqual(self.command(client, '/remember denied', chat_id=456).status_code, 403)
            for header, value in [('Origin', 'https://untrusted.invalid'), ('Host', 'attacker.invalid')]:
                self.assertEqual(self.command(client, '/remember denied', headers={**self.headers, header: value}).status_code, 403)
            self.assertEqual(app.state.memory.list_recent_memory(), [])
            self.assertIsNone(app.state.runner._task)
            self.assertFalse(client.get('/healthz').json()['telegram_polling'])

    def test_memory_documents_restart_and_no_cloud_fallback(self):
        with TestClient(create_app(self.settings, self.model)) as client:
            self.assertEqual(self.command(client, '/remember synthetic record').status_code, 200)
            self.assertIn('synthetic record', self.command(client, '/find synthetic').json()['reply'])
            content = b'synthetic attachment bytes'
            result = client.put('/local/documents/example.txt', content=content, headers=self.headers)
            self.assertEqual(result.status_code, 200)
            document_id = result.json()['id']
            self.assertEqual(client.get('/local/documents/' + document_id, headers=self.headers).content, content)
            self.assertEqual(len(client.get('/local/documents?query=example', headers=self.headers).json()), 1)
            self.model.complete.side_effect = httpx.ConnectError('synthetic unavailable loopback')
            with patch('app.model_client.AzureOpenAIClient') as azure:
                self.assertEqual(self.command(client, '/brief synthetic').status_code, 503)
                azure.assert_not_called()
            self.assertEqual(self.command(client, '/find synthetic').status_code, 200)
            with self.assertRaises(RuntimeError):
                backup(self.root / 'data', self.root / 'online.zip')
        with TestClient(create_app(self.settings, self.model)) as client:
            self.assertIn('synthetic record', self.command(client, '/find synthetic').json()['reply'])
            self.assertEqual(client.get('/local/documents/' + document_id, headers=self.headers).content, content)

    def test_arbiter_approval_and_cohort_desk_compatibility(self):
        with TestClient(create_app(self.settings, self.model)) as client:
            for command in ('/brief', '/prep', '/followup', '/draft', '/task'):
                result = self.command(client, command + ' sign a binding contract')
                self.assertEqual(result.status_code, 200)
                self.assertIn('approval', result.json()['reply'])
            self.model.complete.assert_not_awaited()
            reply = self.command(client, '/cohort desk').json()['reply']
            self.assertIn('apps.powerapps.com', reply)

    def test_recovery_checksums_counts_documents_and_refuses_live_overwrite(self):
        data = self.root / 'data'
        MemoryStore(data / 'nexus_memory.sqlite3').save_memory('synthetic recovery')
        artifacts = data / 'artifacts' / 'documents'
        artifacts.mkdir(parents=True)
        (artifacts / 'synthetic.blob').write_bytes(b'synthetic document')
        archive = self.root / 'backup.zip'
        manifest = backup(data, archive)
        restored = self.root / 'recovered'
        self.assertEqual(restore(archive, restored)['counts'], manifest['counts'])
        self.assertEqual((restored / 'artifacts/documents/synthetic.blob').read_bytes(), b'synthetic document')
        self.assertEqual(len(MemoryStore(restored / 'nexus_memory.sqlite3').search_memory('synthetic')), 1)
        with self.assertRaises(FileExistsError):
            restore(archive, restored)
        corrupt = self.root / 'corrupt.zip'
        with zipfile.ZipFile(archive) as source, zipfile.ZipFile(corrupt, 'w') as target:
            for name in source.namelist():
                target.writestr(name, b'changed' if name.endswith('.blob') else source.read(name))
        with self.assertRaises(ValueError):
            restore(corrupt, self.root / 'corrupt-recovery')
        self.assertFalse((self.root / 'corrupt-recovery').exists())

    def test_recovery_rejects_traversal_and_extra_members(self):
        malicious = self.root / 'malicious.zip'
        with zipfile.ZipFile(malicious, 'w') as archive:
            archive.writestr('../outside.txt', 'synthetic')
            archive.writestr('manifest.json', '{}')
        with self.assertRaises(ValueError):
            restore(malicious, self.root / 'unsafe')
        self.assertFalse((self.root / 'outside.txt').exists())

    def test_single_owner_locks_and_safe_startup(self):
        with FileLease(self.root / 'lease.lock'):
            with self.assertRaises(RuntimeError):
                with FileLease(self.root / 'lease.lock'):
                    self.fail('Second owner acquired the lease')
        for invalid in (replace(self.settings, local_api_token='short'),
                        replace(self.settings, telegram_enabled=True, telegram_bot_token='synthetic'),
                        replace(self.settings, local_artifact_path=str(self.root / 'different')),
                        replace(self.settings, app_insights_connection_string='synthetic')):
            with self.assertRaises(ValueError):
                create_app(invalid, self.model)


class PaidCloudTests(unittest.IsolatedAsyncioTestCase):
    async def test_cloud_requires_exact_unexpired_single_use_approval_and_status_is_free(self):
        from app.azure_openai_client import AzureOpenAIClient
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as root, patch('app.azure_openai_client.AsyncAzureOpenAI'):
            client = AzureOpenAIClient(local_settings(Path(root)))
            client.client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='synthetic approved response'))]))
            with self.assertRaises(PermissionError):
                await client.complete('system', 'request', 10)
            self.assertTrue((await client.probe())['authorization_required'])
            client.client.chat.completions.create.assert_not_awaited()
            approval = PaidJobApproval('synthetic-id', 'operator', job_fingerprint('system', 'request', 10), datetime.now(UTC) + timedelta(minutes=1))
            self.assertEqual(await client.complete('system', 'request', 10, approval=approval), 'synthetic approved response')
            with self.assertRaises(PermissionError):
                await client.complete('system', 'request', 10, approval=approval)
            client.client.chat.completions.create.assert_awaited_once()

    def test_approval_cannot_be_reused_or_applied_to_another_request(self):
        approval = PaidJobApproval('synthetic-approval', 'synthetic-operator', job_fingerprint('system', 'request', 10), datetime.now(UTC) + timedelta(minutes=1))
        with self.assertRaises(PermissionError):
            approval.consume('system', 'different', 10)
        approval.consume('system', 'request', 10)
        with self.assertRaises(PermissionError):
            approval.consume('system', 'request', 10)
        expired = PaidJobApproval('id', 'operator', job_fingerprint('s', 'u', 10), datetime.now(UTC) - timedelta(seconds=1))
        with self.assertRaises(PermissionError):
            expired.consume('s', 'u', 10)
