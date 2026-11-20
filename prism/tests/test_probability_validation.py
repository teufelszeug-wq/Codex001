"""Regression: nested win probabilities must be valid before persistence."""
import unittest
from racecard_forecast_bridge import build_preday_records

class ProbabilityValidation(unittest.TestCase):
    def setUp(self):
        self.card = {
            "race_id": "SYNTHETIC_PROB", "source_id": "synthetic_test_only",
            "source_authenticity_verified": True,
            "scheduled_start_at": "2026-12-01T12:00:00+00:00",
            "horses": [{"horse_id": "H1", "horse_name": "架空一号"}],
        }

    def build(self, value):
        return build_preday_records(
            self.card, [{"horse_id": "H1", "prediction": {"win_probability": value}}],
            forecaster_id="test_baseline", version="test_v1",
            saved_at="2026-11-21T00:00:00+00:00")

    def test_invalid_probabilities_rejected(self):
        for value in (float("nan"), float("inf"), -float("inf"), -0.1, 1.1, True, None, "0.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.build(value)

    def test_valid_boundaries(self):
        for value in (0.0, 0.5, 1.0):
            with self.subTest(value=value):
                self.assertEqual(self.build(value)[0]["prediction"]["win_probability"], value)

if __name__ == "__main__":
    unittest.main()
