import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.local_api import create_app
from test_local_acceptance import local_settings


class LocalBrowserBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.settings = local_settings(Path(self.temporary.name))
        self.model = AsyncMock()
        self.model.probe.return_value = {'healthy': True}
        self.model.complete.return_value = 'Synthetic local response'
        self.headers = {'Authorization': 'Bearer ' + self.settings.local_api_token}

    def test_public_shell_has_no_credentials_and_protects_private_runtime(self):
        with TestClient(create_app(self.settings, self.model)) as client:
            page = client.get('/')
            self.assertEqual(page.status_code, 200)
            self.assertIn('Chat with Nexus', page.text)
            self.assertNotIn(self.settings.local_api_token, page.text)
            self.assertEqual(page.headers['cache-control'], 'no-store')
            self.assertIn("frame-ancestors 'none'", page.headers['content-security-policy'])
            self.assertEqual(client.get('/ui/app.js').status_code, 200)
            self.assertEqual(client.get('/ui/styles.css').status_code, 200)
            self.assertEqual(client.get('/local/runtime').status_code, 401)
            runtime = client.get('/local/runtime', headers=self.headers)
            self.assertEqual(runtime.status_code, 200)
            self.assertEqual(runtime.json()['model'], 'synthetic-model')
            self.assertEqual(runtime.json()['operator_id'], 123)
            self.assertFalse(runtime.json()['telegram_polling'])

    def test_only_exact_same_origin_is_accepted_with_a_valid_bearer(self):
        with TestClient(create_app(self.settings, self.model), base_url='http://127.0.0.1:8765') as client:
            payload = {'chat_id': 123, 'text': '/remember browser synthetic record'}
            good = {**self.headers, 'Origin': 'http://127.0.0.1:8765', 'Sec-Fetch-Site': 'same-origin'}
            self.assertEqual(client.post('/local/command', json=payload, headers=good).status_code, 200)
            for origin in ['null', 'https://127.0.0.1:8765', 'http://127.0.0.1:8766', 'http://localhost:8765', 'https://untrusted.invalid']:
                bad = {**self.headers, 'Origin': origin}
                self.assertEqual(client.post('/local/command', json=payload, headers=bad).status_code, 403)
            for site in ['cross-site', 'same-site']:
                self.assertEqual(client.get('/local/runtime', headers={**self.headers, 'Sec-Fetch-Site': site}).status_code, 403)
            self.assertEqual(client.get('/', headers={'Host': 'untrusted.invalid'}).status_code, 403)
            self.assertEqual(client.get('/local/runtime', headers={'Origin': 'http://127.0.0.1:8765'}).status_code, 401)
            self.assertEqual(len(client.app.state.memory.list_recent_memory()), 1)

    def test_browser_command_uses_ollama_contract_and_existing_memory(self):
        with TestClient(create_app(self.settings, self.model), base_url='http://localhost:8765') as client:
            headers = {**self.headers, 'Origin': 'http://localhost:8765'}
            client.post('/local/command', headers=headers, json={'chat_id': 123, 'text': '/remember synthetic browser project BLUEBIRD-91'})
            reply = client.post('/local/command', headers=headers, json={'chat_id': 123, 'text': '/brief summarize the synthetic browser project BLUEBIRD-91'})
            self.assertEqual(reply.status_code, 200)
            self.assertIn('Synthetic local response', reply.json()['reply'])
            self.assertIn('BLUEBIRD-91', self.model.complete.call_args.args[1])
            self.assertEqual(client.get('/local/runtime', headers=headers).json()['memory_records'], 1)
