"""Regression checks for empty and non-finite forecast payloads."""
import math
import unittest
from racecard_forecast_bridge import build_preday_records

RACECARD = {
    "race_id": "TEST-2026-11-22-01",
    "source_id": "fixture-only",
    "source_authenticity_verified": True,
    "scheduled_start_at": "2026-11-22T12:00:00+09:00",
    "horses": [{"horse_id": "H1", "horse_name": "テスト馬"}],
}

class PredictionPayloadContract(unittest.TestCase):
    def test_invalid_payloads(self):
        for value in ({}, [], "", False, True, math.nan, math.inf, -math.inf):
            with self.subTest(value=repr(value)):
                with self.assertRaises(ValueError):
                    build_preday_records(RACECARD, [{"horse_id": "H1", "prediction": value}],
                        forecaster_id="TEST", version="fixture-v1")

    def test_nonempty_payload(self):
        result = build_preday_records(RACECARD,
            [{"horse_id": "H1", "prediction": {"win_probability": 0.25}}],
            forecaster_id="TEST", version="fixture-v1")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["prediction"]["win_probability"], 0.25)

if __name__ == "__main__":
    unittest.main()
