"""Regression checks for racecard-to-preday bridge using timezone-aware fixtures."""
import unittest
from datetime import datetime, timedelta, timezone
from prism.racecard_forecast_bridge import build_preday_records


class PredayBridgeTimeTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.saved = (now - timedelta(minutes=10)).isoformat()
        self.card = {
            "race_id": "TEST-2026-11-22-01",
            "source_id": "https://www.jra.go.jp/test-only",
            "source_authenticity_verified": True,
            "source_retrieved_at": (now - timedelta(minutes=20)).isoformat(),
            "scheduled_start_at": (now + timedelta(days=1)).isoformat(),
            "horses": [
                {"horse_id": "h1", "horse_name": "テスト馬一"},
                {"horse_id": "h2", "horse_name": "テスト馬二"},
            ],
        }
        self.forecasts = [
            {"horse_id": "h1", "prediction": {"win_probability": 0.6}},
            {"horse_id": "h2", "prediction": {"win_probability": 0.4}},
        ]

    def run_bridge(self, **overrides):
        return build_preday_records(
            overrides.get("card", self.card),
            overrides.get("forecasts", self.forecasts),
            forecaster_id="test-forecaster",
            version="preday-v1",
            saved_at=overrides.get("saved", self.saved),
        )

    def test_valid_full_field(self):
        records = self.run_bridge()
        self.assertEqual(len(records), 2)
        self.assertTrue(all(r["record_type"] == "preday_forecast" for r in records))

    def test_probability_sum_rejected(self):
        forecasts = [
            {"horse_id": "h1", "prediction": {"win_probability": 0.6}},
            {"horse_id": "h2", "prediction": {"win_probability": 0.3}},
        ]
        with self.assertRaisesRegex(ValueError, "sum"):
            self.run_bridge(forecasts=forecasts)

    def test_partial_probabilities_rejected(self):
        forecasts = [
            {"horse_id": "h1", "prediction": {"win_probability": 0.6}},
            {"horse_id": "h2", "prediction": {"rank": 2}},
        ]
        with self.assertRaisesRegex(ValueError, "partial"):
            self.run_bridge(forecasts=forecasts)

    def test_source_after_saved_rejected(self):
        card = dict(self.card, source_retrieved_at=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat())
        with self.assertRaisesRegex(ValueError, "source retrieved after"):
            self.run_bridge(card=card)

    def test_after_start_rejected(self):
        card = dict(self.card, scheduled_start_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat())
        with self.assertRaisesRegex(ValueError, "before scheduled start"):
            self.run_bridge(card=card)

    def test_unverified_source_rejected(self):
        card = dict(self.card, source_authenticity_verified=False)
        with self.assertRaisesRegex(ValueError, "authenticated"):
            self.run_bridge(card=card)


if __name__ == "__main__":
    unittest.main()
