"""Regression checks for Git evidence temporal consistency."""
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_real_races.py"
spec = importlib.util.spec_from_file_location("audit_real_races", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class TemporalEvidenceTests(unittest.TestCase):
    def test_commit_before_claimed_saved_at_is_not_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "PRISM Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            file = repo / "forecast.json"
            payload = dict(race_id="test-race", version=1,
                saved_at="2026-11-15T12:00:00+09:00",
                off_at="2026-11-16T12:00:00+09:00",
                source_refs=["test-source"], records=[{"horse_name":"テスト馬"}])
            file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "forecast.json"], check=True)
            import os
            env = dict(os.environ, GIT_AUTHOR_DATE="2026-11-15T10:00:00+09:00",
                       GIT_COMMITTER_DATE="2026-11-15T10:00:00+09:00")
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "earlier"], check=True, env=env)
            result = mod.audit({"targets":[{"race_id":"test-race","off_at":payload["off_at"]}]}, [file], repo)
            self.assertEqual(result["verified_pre_off_count"], 0)
            self.assertEqual(result["pre_off_candidate_count"], 1)

    def test_boolean_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "forecast.json"
            doc = dict(race_id="r1",version=True,saved_at="2026-11-15T12:00:00+09:00",
                       off_at="2026-11-16T12:00:00+09:00",source_refs=["s"],records=[{}])
            file.write_text(json.dumps(doc), encoding="utf-8")
            result = mod.audit({"targets":[{"race_id":"r1","off_at":doc["off_at"]}]}, [file])
            self.assertEqual(result["pre_off_candidate_count"], 0)
            self.assertEqual(result["rejected_count"], 1)

if __name__ == "__main__":
    unittest.main()
