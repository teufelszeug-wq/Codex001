"""Regression tests for pre-off Git evidence with real local Git repositories."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_real_races.py"
spec = importlib.util.spec_from_file_location("prism_real_race_audit", SCRIPT)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)

class GitEvidenceRegression(unittest.TestCase):
    def test_commit_after_off_does_not_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            def git(*args, env=None):
                import os
                e = os.environ.copy()
                if env: e.update(env)
                return subprocess.run(["git", "-C", str(repo), *args],
                                      check=True, capture_output=True, text=True, env=e)
            git("init")
            git("config", "user.email", "prism-test@example.invalid")
            git("config", "user.name", "PRISM Test")
            file = repo / "forecast.json"
            off = "2026-11-16T12:00:00+09:00"
            file.write_text(json.dumps({
                "race_id": "test-race", "version": 1,
                "saved_at": "2026-11-15T20:00:00+09:00",
                "off_at": off, "source_refs": ["fixture"],
                "records": [{"forecaster_id": "test"}]
            }), encoding="utf-8")
            git("add", "forecast.json")
            git("commit", "-m", "post-off fixture", env={
                "GIT_AUTHOR_DATE": "2026-11-16T13:00:00+09:00",
                "GIT_COMMITTER_DATE": "2026-11-16T13:00:00+09:00"
            })
            result = audit_module.audit(
                {"targets": [{"race_id": "test-race", "off_at": off}]},
                [file], repo)
            self.assertEqual(result["verified_pre_off_count"], 0)
            self.assertEqual(result["pre_off_candidate_count"], 1)

if __name__ == "__main__":
    unittest.main()
