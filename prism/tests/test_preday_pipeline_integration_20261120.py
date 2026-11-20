"""Integration tests for actual preday guard and writer (no simulated predictions)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preday_pipeline import save_preday_record

def sample():
    return {
        "race_id": "TEST-20261121-01",
        "horse_id": "TEST-H001",
        "horse_name": "テスト馬",
        "forecaster_id": "test-forecaster",
        "source_id": "test-fixture",
        "saved_at": "2026-11-20T12:00:00+09:00",
        "version": "preday-v1",
        "scheduled_start_at": "2026-11-21T15:00:00+09:00",
        "source_authenticity_verified": True,
        "record_type": "preday_forecast",
    }

class PredayWriterIntegration(unittest.TestCase):
    def test_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "forecast.json"
            record = sample()
            save_preday_record(record, p, as_of="2026-11-20T13:00:00+09:00")
            self.assertEqual(json.loads(p.read_text(encoding="utf-8")), record)
            with self.assertRaises(FileExistsError):
                save_preday_record(record, p, as_of="2026-11-20T13:00:00+09:00")
            self.assertEqual(json.loads(p.read_text(encoding="utf-8")), record)

    def test_rejects_race_day_record_without_creating_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "forecast.json"
            record = sample()
            record["saved_at"] = "2026-11-21T09:00:00+09:00"
            with self.assertRaises(ValueError):
                save_preday_record(record, p, as_of="2026-11-21T10:00:00+09:00")
            self.assertFalse(p.exists())

    def test_rejects_unverified_source_without_creating_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "forecast.json"
            record = sample()
            record["source_authenticity_verified"] = False
            with self.assertRaises(ValueError):
                save_preday_record(record, p, as_of="2026-11-20T13:00:00+09:00")
            self.assertFalse(p.exists())

if __name__ == "__main__":
    unittest.main()
