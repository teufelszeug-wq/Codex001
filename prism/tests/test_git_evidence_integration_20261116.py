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

    def test_commit_before_off_verifies_and_before_saved_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            import os
            repo = Path(tmp)
            def git(*args, date=None):
                env = os.environ.copy()
                if date:
                    env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
                return subprocess.run(["git", "-C", str(repo), *args],
                                      check=True, capture_output=True, text=True, env=env)
            git("init")
            git("config", "user.email", "prism-test@example.invalid")
            git("config", "user.name", "PRISM Test")
            file = repo / "forecast.json"
            off = "2026-11-16T12:00:00+09:00"
            saved = "2026-11-15T20:00:00+09:00"
            file.write_text(json.dumps({
                "race_id": "test-race", "version": 1,
                "saved_at": saved, "off_at": off,
                "source_refs": ["fixture"],
                "records": [{"forecaster_id": "test"}]
            }), encoding="utf-8")
            git("add", "forecast.json")
            git("commit", "-m", "pre-off fixture",
                date="2026-11-15T21:00:00+09:00")
            targets = {"targets": [{"race_id": "test-race", "off_at": off}]}
            result = audit_module.audit(targets, [file], repo)
            self.assertEqual(result["verified_pre_off_count"], 1)
            self.assertEqual(result["races"][0]["reason"], "GIT_COMMIT_PRE_OFF_VERIFIED")
            self.assertTrue(result["races"][0]["evidence"]["commit_sha"])
            # A later self-reported save time must not be verified by an older commit.
            payload = json.loads(file.read_text(encoding="utf-8"))
            payload["saved_at"] = "2026-11-15T22:00:00+09:00"
            file.write_text(json.dumps(payload), encoding="utf-8")
            git("add", "forecast.json")
            git("commit", "-m", "pre-off later save fixture",
                date="2026-11-15T21:30:00+09:00")
            result = audit_module.audit(targets, [file], repo)
            self.assertEqual(result["verified_pre_off_count"], 0)
            self.assertEqual(result["pre_off_candidate_count"], 1)

if __name__ == "__main__":
    unittest.main()
