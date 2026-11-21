"""Regression: missing probabilities must not be persisted as formal forecasts."""
import tempfile
import unittest
from pathlib import Path
from prism.preday_batch_store import persist_preday_batch


def example():
    return {
        "race_id": "20261122-TOK-11", "horse_id": "h1", "horse_name": "試験馬",
        "forecaster_id": "editorial", "source_id": "verified-fixture",
        "saved_at": "2026-11-21T10:00:00+09:00",
        "version": "preday-v1", "scheduled_start_at": "2026-11-22T15:00:00+09:00",
        "record_type": "preday_forecast", "source_authenticity_verified": True,
    }


class ProbabilityRequiredTests(unittest.TestCase):
    def test_missing_prediction_rejected_without_file(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "win_probability"):
                persist_preday_batch([example()], folder)
            self.assertEqual(list(Path(folder).glob("*.json")), [])

    def test_empty_prediction_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            item = example()
            item["prediction"] = {}
            with self.assertRaisesRegex(ValueError, "win_probability"):
                persist_preday_batch([item], folder)

    def test_complete_probability_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            item = example()
            item["prediction"] = {"win_probability": 1.0}
            self.assertTrue(Path(persist_preday_batch([item], folder)).exists())


if __name__ == "__main__":
    unittest.main()
