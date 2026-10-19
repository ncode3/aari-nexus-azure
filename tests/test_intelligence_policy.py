import unittest
from app.intelligence_policy import prototype_api_allowed, telegram_chat_allowed


class IntelligencePolicyTests(unittest.TestCase):
    def test_empty_and_unlisted_chats_denied(self):
        self.assertFalse(telegram_chat_allowed(1, set()))
        self.assertFalse(telegram_chat_allowed(2, {1}))
        self.assertTrue(telegram_chat_allowed(1, {1}))

    def test_missing_settings_denied(self):
        self.assertFalse(prototype_api_allowed({}))
        self.assertFalse(prototype_api_allowed({"APP_ENV": "local"}))

    def test_deployed_environments_denied_even_with_flag(self):
        for env in ["dev", "staging", "prod", "production", ""]:
            self.assertFalse(prototype_api_allowed({"APP_ENV": env, "NEXUS_LOCAL_EMAIL_PROTOTYPE": "true"}))

    def test_local_and_test_require_explicit_opt_in(self):
        for env in ["local", "test"]:
            self.assertTrue(prototype_api_allowed({"APP_ENV": env, "NEXUS_LOCAL_EMAIL_PROTOTYPE": "true"}))
            self.assertFalse(prototype_api_allowed({"APP_ENV": env, "NEXUS_LOCAL_EMAIL_PROTOTYPE": "false"}))
