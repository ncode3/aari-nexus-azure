from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ollama_local_client import OllamaLocalClient, validate_ollama_url


class OllamaLocalClientTests(unittest.IsolatedAsyncioTestCase):
    def test_local_only(self):
        for url in (
            "http://0.0.0.0:11434",
            "http://192.168.1.2:11434",
            "https://example.com:11434",
            "http://localhost:11434/path",
            "http://user:pass@localhost:11434",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_ollama_url(url)
        self.assertEqual(validate_ollama_url("http://127.0.0.1:11434"),
                         "http://127.0.0.1:11434")

    async def test_complete(self):
        response = MagicMock()
        response.json.return_value = {"message": {"content": "local answer"}}
        response.raise_for_status.return_value = None
        client = AsyncMock()
        client.post.return_value = response
        manager = AsyncMock()
        manager.__aenter__.return_value = client
        with patch("app.ollama_local_client.httpx.AsyncClient", return_value=manager):
            result = await OllamaLocalClient("qwen-test").complete("system", "question")
        self.assertEqual(result, "local answer")
        self.assertEqual(client.post.await_args.kwargs["json"]["stream"], False)

    async def test_missing_content_fails(self):
        response = MagicMock()
        response.json.return_value = {}
        client = AsyncMock()
        client.post.return_value = response
        manager = AsyncMock()
        manager.__aenter__.return_value = client
        with patch("app.ollama_local_client.httpx.AsyncClient", return_value=manager):
            with self.assertRaises(ValueError):
                await OllamaLocalClient("qwen-test").brief("question")


if __name__ == "__main__":
    unittest.main()
