"""Regression: no unpredicted runner may be persisted as a complete field."""
import unittest
from racecard_forecast_bridge import build_preday_records

CARD = {
    "source_authenticity_verified": True,
    "race_id": "TEST_20261122_01",
    "source_id": "fixture-only",
    "scheduled_start_at": "2026-11-22T12:00:00+09:00",
    "horses": [
        {"horse_id": "H1", "horse_name": "TEST HORSE 1"},
        {"horse_id": "H2", "horse_name": "TEST HORSE 2"},
    ],
}

class MissingPredictionTests(unittest.TestCase):
    def build(self, forecasts):
        return build_preday_records(
            CARD, forecasts, forecaster_id="test_ai",
            version="preday_v1", saved_at="2026-11-21T03:00:00+00:00"
        )

    def test_missing_prediction_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing prediction"):
            self.build([{"horse_id": "H1", "prediction": {"win_probability": 0.4}},
                        {"horse_id": "H2"}])

    def test_null_prediction_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing prediction"):
            self.build([{"horse_id": "H1", "prediction": {}},
                        {"horse_id": "H2", "prediction": None}])

    def test_complete_field_accepted(self):
        result = self.build([{"horse_id": "H1", "prediction": {"win_probability": 0.4}},
                             {"horse_id": "H2", "prediction": {"win_probability": 0.6}}])
        self.assertEqual(len(result), 2)
        self.assertEqual({x["horse_name"] for x in result}, {"TEST HORSE 1", "TEST HORSE 2"})

if __name__ == "__main__":
    unittest.main()
