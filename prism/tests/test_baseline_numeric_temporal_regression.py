"""Regression checks for baseline score stability and temporal boundaries.

Synthetic data only; not an official prediction or model calibration.
"""
import unittest
from datetime import datetime, timedelta, timezone
from prerace_baseline import forecast_field


class BaselineNumericalAndTemporalRegression(unittest.TestCase):
    def setUp(self):
        self.cutoff = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
        self.start = self.cutoff + timedelta(days=2)
        self.card = {
            "race_id": "SYNTHETIC_NUMERIC",
            "source_authenticity_verified": True,
            "scheduled_start_at": self.start.isoformat(),
            "horses": [
                {"horse_id": "H1", "horse_name": "架空一号"},
                {"horse_id": "H2", "horse_name": "架空二号"},
            ],
        }

    def rows(self, first=1000.0, second=-1000.0):
        return [
            {"horse_id": "H1", "observed_at": self.cutoff.isoformat(), "pre_race_score": first},
            {"horse_id": "H2", "observed_at": self.cutoff.isoformat(), "pre_race_score": second},
        ]

    def test_extreme_finite_scores_normalize_without_overflow(self):
        forecasts = forecast_field(self.card, self.rows(), cutoff_at=self.cutoff.isoformat())
        probabilities = [r["prediction"]["win_probability"] for r in forecasts]
        self.assertAlmostEqual(sum(probabilities), 1.0)
        self.assertGreater(probabilities[0], probabilities[1])
        self.assertTrue(all(0.0 <= p <= 1.0 for p in probabilities))

    def test_equal_scores_yield_equal_probabilities(self):
        forecasts = forecast_field(self.card, self.rows(2.0, 2.0), cutoff_at=self.cutoff.isoformat())
        self.assertEqual([r["prediction"]["win_probability"] for r in forecasts], [0.5, 0.5])

    def test_feature_one_microsecond_after_cutoff_rejected(self):
        rows = self.rows()
        rows[0]["observed_at"] = (self.cutoff + timedelta(microseconds=1)).isoformat()
        with self.assertRaises(ValueError):
            forecast_field(self.card, rows, cutoff_at=self.cutoff.isoformat())

    def test_cutoff_at_race_start_rejected(self):
        with self.assertRaises(ValueError):
            forecast_field(self.card, self.rows(), cutoff_at=self.start.isoformat())


if __name__ == "__main__":
    unittest.main()
