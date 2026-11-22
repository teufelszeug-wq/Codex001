"""Regression: a complete win market must sum to one before persistence.

Synthetic racecard only. This does not authenticate official race data.
"""
import unittest
from racecard_forecast_bridge import build_preday_records


class WinMarketCoherenceTests(unittest.TestCase):
    def setUp(self):
        self.card = {
            "race_id": "TEST_MARKET_R01",
            "source_id": "synthetic_test_only",
            "source_authenticity_verified": True,
            "scheduled_start_at": "2026-11-22T10:00:00+09:00",
            "source_retrieved_at": "2026-11-21T09:00:00+09:00",
            "horses": [
                {"horse_id": "H1", "horse_name": "架空一号"},
                {"horse_id": "H2", "horse_name": "架空二号"},
            ],
        }

    def rows(self, a, b):
        return [
            {"horse_id": "H1", "prediction": a},
            {"horse_id": "H2", "prediction": b},
        ]

    def convert(self, rows):
        return build_preday_records(
            self.card, rows, forecaster_id="test_model",
            version="test_v1", saved_at="2026-11-21T10:00:00+09:00")

    def test_normalized_market_passes(self):
        records = self.convert(self.rows(
            {"win_probability": 0.25}, {"win_probability": 0.75}))
        self.assertEqual(len(records), 2)

    def test_non_normalized_market_fails(self):
        with self.assertRaisesRegex(ValueError, "sum"):
            self.convert(self.rows(
                {"win_probability": 0.2}, {"win_probability": 0.3}))

    def test_partial_probability_coverage_fails(self):
        with self.assertRaisesRegex(ValueError, "missing win_probability"):
            self.convert(self.rows(
                {"win_probability": 0.4}, {"rank": 2}))

    def test_non_probability_forecasts_rejected_by_current_contract(self):
        with self.assertRaisesRegex(ValueError, "missing win_probability"):
            self.convert(self.rows({"rank": 1}, {"rank": 2}))


if __name__ == "__main__":
    unittest.main()
