"""Regression tests for Japanese calendar-day preday cutoff."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from prism.racecard_forecast_bridge import build_preday_records

JST = timezone(timedelta(hours=9))

class PredayJstBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.racecard = {
            "source_authenticity_verified": True,
            "race_id": "test-20261122-01",
            "source_id": "verified-fixture-not-official",
            "scheduled_start_at": "2026-11-22T10:00:00+09:00",
            "source_retrieved_at": "2026-11-21T08:00:00+09:00",
            "horses": [{"horse_id": "h1", "horse_name": "Fixture Horse"}],
        }
        self.forecasts = [{"horse_id": "h1", "prediction": {"win_probability": 1.0}}]

    def build(self, stamp):
        return build_preday_records(self.racecard, self.forecasts,
            forecaster_id="fixture", version="test-v1", saved_at=stamp)

    def test_previous_day_jst_accepted(self):
        self.assertEqual(len(self.build("2026-11-21T23:59:59+09:00")), 1)

    def test_race_day_morning_rejected(self):
        with self.assertRaisesRegex(ValueError, "before race day in JST"):
            self.build("2026-11-22T09:00:00+09:00")

    def test_utc_previous_day_but_jst_race_day_rejected(self):
        with self.assertRaisesRegex(ValueError, "before race day in JST"):
            self.build("2026-11-21T15:30:00+00:00")

if __name__ == "__main__":
    unittest.main()
