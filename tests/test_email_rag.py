import tempfile
import unittest
from pathlib import Path
from app.email_rag import EmailRAG

class EmailRAGTests(unittest.TestCase):
    def test_ingest_search_and_upsert(self):
        with tempfile.TemporaryDirectory() as tmp:
            rag = EmailRAG(Path(tmp) / "rag.sqlite")
            doc = {"id":"m1","thread_id":"t1","subject":"QTS grant","body":"Awarded fifteen thousand dollars","source_url":"https://mail.google.com/mail/u/0/#all/t1"}
            self.assertEqual(rag.ingest([doc]),1)
            self.assertEqual(len(rag.search("QTS grant")),1)
            doc["body"] = "QTS check received"
            rag.ingest([doc])
            self.assertEqual(len(rag.search("received")),1)
            self.assertEqual(len(rag.search("fifteen")),0)
            self.assertEqual(len(rag.evidence_prompt("received")["evidence"]),1)
    def test_empty_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(EmailRAG(Path(tmp)/"x.db").search("?!"),[])
if __name__=="__main__":
    unittest.main()
