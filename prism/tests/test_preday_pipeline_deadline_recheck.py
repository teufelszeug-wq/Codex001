"""Regression: stale injected execution clock cannot save a pre-day record."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from prism_engine.preday_pipeline import run


class DeadlineRecheckTests(unittest.TestCase):
    def test_rejects_after_inference_if_real_day_has_passed(self):
        today = datetime.now(timezone.utc).date()
        cutoff = datetime.combine(today - timedelta(days=1), datetime.min.time(), timezone.utc)
        started = cutoff - timedelta(days=1)
        payload = {
            "raw": {
                "mode": "REAL",
                "source": {"source_id": "UNVERIFIED-REGRESSION"},
                "race": {"cutoff": cutoff.isoformat()},
                "runners": [{"horse_id": "H1"}],
            },
            "horse_names": {"H1": "テスト馬"},
            "predictor_id": "main",
            "version": "test",
        }
        with patch("prism_engine.preday_pipeline.predict", return_value={"race_id": "R1"}) as predict_mock, patch(
            "prism_engine.preday_pipeline.persist_prediction_now"
        ) as save_mock:
            with self.assertRaisesRegex(ValueError, "passed during prediction"):
                run(payload, "/tmp/prism-regression-unused", now=started)
            predict_mock.assert_called_once()
            save_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
