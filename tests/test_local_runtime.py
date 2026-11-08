import os
import tempfile
import unittest
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
from app.config import get_settings, validate_settings
from app.local import configure_local_environment
from app.model_client import create_model_client
from app.ollama_local_client import OllamaLocalClient
from app.telemetry import upload_artifact
from app.memory import MemoryStore
from app.commands import handle_operational_command


class LocalRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def settings(self):
        with patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'synthetic',
                'BOT_ALLOWED_CHAT_IDS': '123', 'OLLAMA_MODEL': 'qwen-test'}, clear=True), \
                patch('app.local.load_dotenv'):
            configure_local_environment()
            return get_settings()

    def test_local_starts_without_azure_credentials(self):
        settings = self.settings()
        validate_settings(settings)
        with patch('app.model_client.AzureOpenAIClient') as azure:
            self.assertIsInstance(create_model_client(settings), OllamaLocalClient)
            azure.assert_not_called()

    def test_local_profile_clears_inherited_cloud_services(self):
        with patch.dict(os.environ, {'AZURE_KEY_VAULT_URI':'https://invalid',
                'AZURE_OPENAI_API_KEY':'synthetic', 'COHORT_GRAPH_ENABLED':'true',
                'APPLICATIONINSIGHTS_CONNECTION_STRING':'synthetic'}, clear=True), \
                patch('app.local.load_dotenv'):
            configure_local_environment()
            self.assertEqual(os.environ['AZURE_KEY_VAULT_URI'], '')
            self.assertEqual(os.environ['AZURE_OPENAI_API_KEY'], '')
            self.assertEqual(os.environ['COHORT_GRAPH_ENABLED'], 'false')
            self.assertEqual(os.environ['APPLICATIONINSIGHTS_CONNECTION_STRING'], '')

    def test_local_requires_authorized_chats_and_model(self):
        settings = self.settings()
        for bad in (replace(settings, bot_allowed_chat_ids=set()),
                    replace(settings, ollama_model=''),
                    replace(settings, model_provider='typo'),
                    replace(settings, ollama_base_url='http://example.org:11434')):
            with self.assertRaises(ValueError):
                validate_settings(bad)

    async def test_local_failure_does_not_call_cloud(self):
        model = create_model_client(self.settings())
        with patch('app.ollama_local_client.httpx.AsyncClient') as client, \
                patch('app.model_client.AzureOpenAIClient') as azure:
            client.return_value.__aenter__.return_value.post.side_effect = httpx.ConnectError('offline')
            with self.assertRaises(httpx.ConnectError):
                await model.brief('synthetic request')
            azure.assert_not_called()

    async def test_local_artifact_and_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            settings = replace(self.settings(), local_artifact_path=root)
            with patch('app.telemetry.BlobServiceClient') as blob:
                path = await upload_artifact(settings, 'briefs', 'brief.json', {'type':'synthetic'})
                self.assertTrue(Path(path).is_file())
                blob.assert_not_called()
                for kind in ('../escape', '..', '/tmp', 'foo\\bar'):
                    with self.assertRaises(ValueError):
                        await upload_artifact(settings, kind, 'a.json', {})

    async def test_memory_survives_reopen(self):
        with tempfile.TemporaryDirectory() as root:
            settings = self.settings()
            path = Path(root) / 'memory.sqlite3'
            store = MemoryStore(path)
            await handle_operational_command('/remember', 'synthetic local project',
                settings, create_model_client(settings), store)
            reopened = MemoryStore(path)
            self.assertEqual(len(reopened.search_memory('synthetic')), 1)
            result = await handle_operational_command('/find', 'synthetic', settings,
                create_model_client(settings), reopened)
            self.assertIn('synthetic local project', result)

class BackupTests(unittest.TestCase):
    def test_backup_restores_memory_and_refuses_overwrite(self):
        import sqlite3
        import zipfile
        from scripts.backup_local import backup
        with tempfile.TemporaryDirectory() as root:
            data = Path(root) / 'data'
            store = MemoryStore(data / 'nexus_memory.sqlite3')
            store.save_memory('synthetic backup check')
            artifacts = data / 'artifacts'
            artifacts.mkdir()
            (artifacts / 'example.json').write_text('{}')
            destination = Path(root) / 'backup.zip'
            backup(data, destination)
            with self.assertRaises(FileExistsError):
                backup(data, destination)
            restore = Path(root) / 'restore'
            with zipfile.ZipFile(destination) as archive:
                archive.extractall(restore)
            restored = MemoryStore(restore / 'nexus_memory.sqlite3')
            self.assertEqual(len(restored.search_memory('synthetic')), 1)
            self.assertEqual((restore / 'artifacts/example.json').read_text(), '{}')
            with closing(sqlite3.connect(restored.db_path)) as connection:
                self.assertEqual(connection.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
