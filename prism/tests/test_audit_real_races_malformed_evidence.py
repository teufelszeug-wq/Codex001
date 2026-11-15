"""Regression checks for malformed real-race forecast evidence."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "audit_real_races.py"
spec = importlib.util.spec_from_file_location("audit_real_races", MODULE)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)

class AuditMalformedEvidenceTests(unittest.TestCase):
    def test_malformed_records_and_source_refs_are_rejected(self):
        target = {"targets": [{"race_id": "test-race", "off_at": "2026-11-16T15:00:00+09:00"}]}
        base = {
            "race_id": "test-race", "version": 1,
            "saved_at": "2026-11-15T18:00:00+09:00",
            "off_at": "2026-11-16T15:00:00+09:00",
            "source_refs": ["official:racecard"], "records": [{"forecaster_id": "test"}]
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "forecast.json"
            for field, value in (("records", ["not-an-object"]), ("source_refs", [None])):
                bad = dict(base, **{field: value})
                p.write_text(json.dumps(bad), encoding="utf-8")
                result = audit_module.audit(target, [p])
                self.assertEqual(result["verified_pre_off_count"], 0)
                self.assertEqual(result["rejected_count"], 1)
                self.assertIn(field, result["rejected_files"][0]["reason"])

if __name__ == "__main__":
    unittest.main()
