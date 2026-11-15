"""Regression tests for rejected evidence visibility in real-race audit."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_real_races.py"
spec = importlib.util.spec_from_file_location("prism_real_race_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class RejectedEvidenceTests(unittest.TestCase):
    def test_bad_json_is_reported_without_preoff_credit(self):
        targets = {"targets":[{"race_id":"R1","off_at":"2026-11-16T15:00:00+09:00"}]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "invalid.json"
            path.write_text("{bad", encoding="utf-8")
            result = module.audit(targets, [path])
        self.assertEqual(result["verified_pre_off_count"], 0)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(result["rejected_files"][0]["error_type"], "JSONDecodeError")

    def test_post_off_evidence_is_reported(self):
        targets = {"targets":[{"race_id":"R1","off_at":"2026-11-16T15:00:00+09:00"}]}
        doc = {"race_id":"R1","version":1,"saved_at":"2026-11-16T15:01:00+09:00",
               "off_at":"2026-11-16T15:00:00+09:00","source_refs":["official"],"records":[{"horse_name":"架空馬"}]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "late.json"
            path.write_text(json.dumps(doc,ensure_ascii=False),encoding="utf-8")
            result = module.audit(targets,[path])
        self.assertEqual(result["verified_pre_off_count"],0)
        self.assertEqual(result["rejected_count"],1)
        self.assertIn("pre-off timestamp",result["rejected_files"][0]["reason"])

if __name__ == "__main__":
    unittest.main()
