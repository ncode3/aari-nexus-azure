from __future__ import annotations

import unittest

from app.arbiter import NexusArbiter
from app.document_flow import summarize_document_flow
from app.intake import build_student_intake_record


class ArbiterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.arbiter = NexusArbiter()

    def test_authorize_known_command(self) -> None:
        decision = self.arbiter.authorize_command("/brief", " Explain   AARI Nexus ")
        self.assertEqual(decision.command, "/brief")
        self.assertEqual(decision.prompt, "Explain AARI Nexus")

    def test_reject_unknown_command(self) -> None:
        with self.assertRaises(ValueError):
            self.arbiter.authorize_command("/unknown", "")

    def test_redact_sensitive_fields(self) -> None:
        redacted = self.arbiter.redact_fields({"chat_id": 12345, "prompt": "secret", "command": "/brief"})
        self.assertEqual(redacted["prompt"], "[redacted]")
        self.assertNotEqual(redacted["chat_id"], 12345)
        self.assertEqual(redacted["command"], "/brief")

    def test_intake_document_flow(self) -> None:
        record = build_student_intake_record("student-001", ["resume.pdf", "transcript.pdf"], "intake/student-001")
        summary = summarize_document_flow(record)
        self.assertEqual(summary["document_count"], 2)
        self.assertIn("resume", summary["document_types"])
        self.assertIn("transcript", summary["document_types"])


if __name__ == "__main__":
    unittest.main()
