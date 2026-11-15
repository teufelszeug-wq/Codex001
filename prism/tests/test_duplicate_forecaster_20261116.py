"""Regression checks for duplicate forecasters in one version."""
import unittest
from prism.scripts.audit_real_races import audit

class DuplicateForecasterAuditTest(unittest.TestCase):
    def test_duplicate_forecaster_rejected(self):
        targets = {"targets": [{"race_id": "20261117_TEST_01", "off_at": "2026-11-17T15:00:00+09:00"}]}
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "forecast.json"
            f.write_text(json.dumps({
                "race_id": "20261117_TEST_01", "version": 1,
                "saved_at": "2026-11-16T15:00:00+09:00",
                "off_at": "2026-11-17T15:00:00+09:00",
                "source_refs": ["fixture:synthetic"],
                "records": [
                    {"forecaster_id": "RIO"},
                    {"forecaster_id": " RIO "}
                ]
            }), encoding="utf-8")
            result = audit(targets, [f])
            self.assertEqual(result["pre_off_candidate_count"], 0)
            self.assertEqual(result["verified_pre_off_count"], 0)
            self.assertEqual(result["rejected_count"], 1)
            self.assertIn("duplicate forecaster_id", result["rejected_files"][0]["reason"])

if __name__ == "__main__":
    unittest.main()
