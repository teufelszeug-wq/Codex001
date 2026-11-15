"""Regression: an unverified duplicate cannot downgrade a verified race."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_real_races.py"
spec = importlib.util.spec_from_file_location("audit_real_races", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DuplicateEvidenceTest(unittest.TestCase):
    def test_later_unverified_candidate_does_not_erase_verified_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "race_id": "R001", "version": 1,
                "saved_at": "2026-11-15T10:00:00+09:00",
                "off_at": "2026-11-16T12:00:00+09:00",
                "source_refs": ["official-entry"], "records": [{"forecaster_id": "A"}],
            }
            first, second = root / "first.json", root / "second.json"
            for file in (first, second):
                file.write_text(json.dumps(payload), encoding="utf-8")
            targets = {"targets": [{"race_id": "R001", "off_at": payload["off_at"]}]}
            evidence = {"commit_sha": "abc123", "committed_at": "2026-11-15T11:00:00+09:00"}
            with patch.object(module, "git_pre_off_evidence", side_effect=[evidence, None]):
                result = module.audit(targets, [first, second], root)
            self.assertEqual(result["verified_pre_off_count"], 1)
            self.assertTrue(result["races"][0]["pre_off_verified"])
            self.assertEqual(result["races"][0]["evidence"], evidence)
            self.assertEqual(result["races"][0]["reason"], "GIT_COMMIT_PRE_OFF_VERIFIED")
            self.assertEqual(result["pre_off_candidate_count"], 2)


if __name__ == "__main__":
    unittest.main()
