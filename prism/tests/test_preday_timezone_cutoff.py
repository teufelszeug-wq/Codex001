"""Regression: a timezone-naive cutoff must not be interpreted in host local time."""
from datetime import datetime, timezone
from unittest.mock import patch
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prism_engine.preday_pipeline import run


class PredayTimezoneTest(unittest.TestCase):
    def test_naive_cutoff_rejected_before_predict_or_write(self):
        payload = {
            "raw": {
                "mode": "RESEARCH",
                "runners": [{"horse_id": "horse-a"}],
                "source": {"source_id": "non-synthetic-provenance"},
                "race": {"cutoff": "2026-11-21T12:00:00"},
            },
            "horse_names": {"horse-a": "テスト馬"},
            "predictor_id": "main",
            "version": "v1",
        }
        with patch("prism_engine.preday_pipeline.predict") as predict:
            with self.assertRaisesRegex(ValueError, "timezone offset"):
                run(payload, "/tmp/prism-timezone-test", now=datetime(2026, 11, 20, 1, tzinfo=timezone.utc))
            predict.assert_not_called()


if __name__ == "__main__":
    unittest.main()
