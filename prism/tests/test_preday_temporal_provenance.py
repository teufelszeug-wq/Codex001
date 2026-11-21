"""Regression checks for preday temporal provenance."""
import unittest
from datetime import datetime, timedelta, timezone
from racecard_forecast_bridge import build_preday_records

class PredayTemporalTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.start = now + timedelta(days=2)
        self.saved = now - timedelta(minutes=1)
        self.card = {
            "race_id": "TEST-TEMPORAL-01", "source_id": "fixture",
            "source_authenticity_verified": True,
            "scheduled_start_at": self.start.isoformat(),
            "source_retrieved_at": (self.saved - timedelta(hours=1)).isoformat(),
            "horses": [{"horse_id": "h1", "horse_name": "テスト馬"}],
        }
        self.predictions = [{"horse_id": "h1", "prediction": {"win_probability": 1.0}}]

    def run_bridge(self, saved):
        return build_preday_records(self.card, self.predictions,
            forecaster_id="test", version="preday-v1", saved_at=saved)

    def test_valid_preday(self):
        self.assertEqual(len(self.run_bridge(self.saved.isoformat())), 1)

    def test_at_start_rejected(self):
        with self.assertRaisesRegex(ValueError, "before scheduled start"):
            self.run_bridge(self.start.isoformat())

    def test_after_start_rejected(self):
        with self.assertRaisesRegex(ValueError, "before scheduled start"):
            self.run_bridge((self.start + timedelta(seconds=1)).isoformat())

    def test_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.run_bridge(self.saved.replace(tzinfo=None).isoformat())

    def test_source_after_saved_rejected(self):
        self.card["source_retrieved_at"] = datetime.now(timezone.utc).isoformat()
        with self.assertRaisesRegex(ValueError, "source retrieved after"):
            self.run_bridge(self.saved.isoformat())

    def test_future_saved_rejected(self):
        with self.assertRaisesRegex(ValueError, "future"):
            self.run_bridge((datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())

if __name__ == "__main__":
    unittest.main()
