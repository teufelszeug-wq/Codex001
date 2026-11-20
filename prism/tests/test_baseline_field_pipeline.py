"""Contract tests for baseline-to-preday orchestration (mocked dependencies)."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from baseline_field_pipeline import persist_baseline_field


class BaselineFieldPipelineTest(unittest.TestCase):
    def test_wiring(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with patch("baseline_field_pipeline.forecast_field", return_value=[{"horse_id": "h1", "prediction": {"win_probability": 1.0}}]) as forecast, patch("baseline_field_pipeline.persist_verified_field", return_value=["saved.json"]) as persist:
            self.assertEqual(persist_baseline_field({}, [], ".", cutoff_at=cutoff), ["saved.json"])
            forecast.assert_called_once()
            persist.assert_called_once()

    def test_future_cutoff_rejected(self):
        cutoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "future"):
            persist_baseline_field({}, [], ".", cutoff_at=cutoff)

    def test_naive_cutoff_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            persist_baseline_field({}, [], ".", cutoff_at="2026-11-20T12:00:00")

    def test_as_of_override_rejected(self):
        with self.assertRaisesRegex(ValueError, "override"):
            persist_baseline_field({}, [], ".", cutoff_at="2026-11-20T12:00:00Z", as_of=datetime.now(timezone.utc))


if __name__ == "__main__":
    unittest.main()
