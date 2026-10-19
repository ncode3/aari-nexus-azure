"""HTTP regression suite; requires repository FastAPI/httpx dependencies."""
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.email_rag_api import authorize, router


class EmailApiSecurityTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def requests(self, token="local-test-token"):
        headers = {"x-nexus-token": token} if token is not None else {}
        return [
            self.client.get("/internal/email-intelligence/funding", headers=headers),
            self.client.post("/internal/email-intelligence/retrieve", json={"question": "QTS grant"}, headers=headers),
            self.client.post("/internal/email-intelligence/ingest", json={"documents": []}, headers=headers),
        ]

    def test_deployed_routes_deny_even_matching_shared_token(self):
        for env in ["dev", "staging", "production"]:
            with patch.dict("os.environ", {"APP_ENV": env, "NEXUS_LOCAL_EMAIL_PROTOTYPE": "true",
                                          "NEXUS_EMAIL_INTELLIGENCE_TOKEN": "local-test-token"}, clear=True), \
                 patch("app.email_rag_api.rag") as database, \
                 patch("app.email_rag_api.build_funding_dashboard") as funding:
                self.assertEqual([r.status_code for r in self.requests()], [503, 503, 503])
                database.assert_not_called()
                funding.assert_not_called()

    def test_local_bad_or_missing_token_cannot_read_or_write(self):
        with patch.dict("os.environ", {"APP_ENV": "test", "NEXUS_LOCAL_EMAIL_PROTOTYPE": "true",
                                      "NEXUS_EMAIL_INTELLIGENCE_TOKEN": "local-test-token"}, clear=True), \
             patch("app.email_rag_api.rag") as database, \
             patch("app.email_rag_api.build_funding_dashboard") as funding:
            for token, status in [(None, 401), ("wrong", 403)]:
                self.assertEqual([r.status_code for r in self.requests(token)], [status] * 3)
            with self.assertRaises(HTTPException) as error:
                authorize("non-ascii-\u00e9")
            self.assertEqual(error.exception.status_code, 403)
            database.assert_not_called()
            funding.assert_not_called()

    def test_explicit_local_opt_in_still_allows_fixture_use(self):
        with patch.dict("os.environ", {"APP_ENV": "test", "NEXUS_LOCAL_EMAIL_PROTOTYPE": "true",
                                      "NEXUS_EMAIL_INTELLIGENCE_TOKEN": "local-test-token"}, clear=True), \
             patch("app.email_rag_api.build_funding_dashboard", return_value={"fixture": True}):
            response = self.client.get("/internal/email-intelligence/funding", headers={"x-nexus-token": "local-test-token"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"fixture": True})
