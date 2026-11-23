import unittest
from forecast_snapshot_gate import validate_snapshot

BASE = dict(race_id="20261123-JRA-TOKYO-11", forecaster_id="paper",
            horse_name="TEST", source="official", version="v1",
            saved_at="2026-11-22T12:00:00+09:00", status="pick",
            mark="◎", evidence_ids=["source-1"])
OFF = "2026-11-23T15:30:00+09:00"

class TestGate(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_snapshot(BASE, OFF), BASE)
    def test_post_race(self):
        with self.assertRaisesRegex(ValueError, "not a pre-race"):
            validate_snapshot(dict(BASE, saved_at=OFF), OFF)
    def test_naive_time(self):
        with self.assertRaisesRegex(ValueError, "timezone required"):
            validate_snapshot(dict(BASE, saved_at="2026-11-22T12:00:00"), OFF)
    def test_missing_source(self):
        with self.assertRaisesRegex(ValueError, "missing source"):
            validate_snapshot(dict(BASE, source=""), OFF)
    def test_missing_evidence(self):
        with self.assertRaisesRegex(ValueError, "evidence IDs"):
            validate_snapshot(dict(BASE, evidence_ids=[]), OFF)
    def test_pass(self):
        self.assertEqual(validate_snapshot(dict(BASE, status="pass", mark=None), OFF)["status"], "pass")
    def test_pass_mark(self):
        with self.assertRaisesRegex(ValueError, "pass cannot"):
            validate_snapshot(dict(BASE, status="pass"), OFF)
    def test_no_mutation(self):
        out = validate_snapshot(BASE, OFF)
        out["evidence_ids"].append("changed")
        self.assertEqual(BASE["evidence_ids"], ["source-1"])

if __name__ == "__main__":
    unittest.main()
