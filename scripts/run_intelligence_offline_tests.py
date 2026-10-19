"""Dependency-free contract/regression tests. No Azure, HTTP or SQL server access."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
suite = unittest.TestSuite()
loader = unittest.TestLoader()
for pattern in ("test_00_fundraising_acceptance.py", "test_intelligence_policy.py",
                "test_intelligence_plan.py", "test_existing_sql_binding.py", "test_email_rag.py", "test_email_intelligence.py"):
    suite.addTests(loader.discover(str(ROOT / "tests"), pattern=pattern))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
