"""Regression tests for pre-race publication time gates.

Run from repository root:
    python -m unittest discover -s prism/tests -p 'test_verified_pre_day_clock.py' -v
These tests do not require official data and must not be counted as real forecasts.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from prism.scripts import run_verified_pre_day as runner


class PreDayClockGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.card = {
            "off_at": (self.now + timedelta(hours=2)).isoformat(),
            "active_runners": [{"horse_no": 1, "horse_number": "1", "horse_id": "H1"}],
        }
        self.kwargs = dict(
            venue="TEST", surface="turf", distance_m=1600,
            direction="right", class_rating=1, barrier_count=1,
            output_dir="/tmp/prism-clock-test", predictor_id="test",
            version="test", source="test", source_evidence={},
            now=self.now.isoformat(),
        )

    def invoke(self, locked_at):
        with patch.object(runner, "validate_engine_input"), patch.object(
            runner, "assemble_engine_input"
        ) as assemble, patch.object(runner, "predict") as predict, patch.object(
            runner, "publish_engine_lock"
        ) as publish:
            with self.assertRaises(ValueError):
                runner.run(self.card, {}, locked_at=locked_at, **self.kwargs)
            assemble.assert_not_called()
            predict.assert_not_called()
            publish.assert_not_called()

    def test_future_cutoff_cannot_be_published(self):
        self.invoke((self.now + timedelta(minutes=1)).isoformat())

    def test_naive_cutoff_is_rejected(self):
        self.invoke(self.now.replace(tzinfo=None).isoformat())

    def test_naive_off_time_is_rejected_before_inference(self):
        self.card["off_at"] = (self.now + timedelta(hours=2)).replace(tzinfo=None).isoformat()
        self.invoke((self.now - timedelta(hours=1)).isoformat())

    def test_inference_crossing_off_time_never_publishes(self):
        # An initially valid lock must not be published if inference finishes late.
        start = self.now
        self.card["off_at"] = (start + timedelta(seconds=2)).isoformat()
        with patch.object(runner, "validate_engine_input"), patch.object(
            runner, "assemble_engine_input", return_value=({}, {"H1": "Test Horse"})
        ), patch.object(runner, "predict", return_value={}) as predict, patch.object(
            runner, "publish_engine_lock"
        ) as publish, patch.object(runner, "datetime", wraps=datetime) as clock:
            clock.now.side_effect = [start, start + timedelta(seconds=3)]
            kwargs = dict(self.kwargs)
            kwargs["now"] = None
            with self.assertRaisesRegex(ValueError, "prediction completed after off time"):
                runner.run(
                    self.card, {}, locked_at=(start - timedelta(hours=1)).isoformat(),
                    **kwargs
                )
            predict.assert_called_once()
            publish.assert_not_called()

    def test_injected_precheck_clock_cannot_backdate_publication(self):
        # A deterministic precheck timestamp must never become saved_at.
        start = self.now
        self.card["off_at"] = (start + timedelta(seconds=2)).isoformat()
        with patch.object(runner, "validate_engine_input"), patch.object(
            runner, "assemble_engine_input", return_value=({}, {"H1": "Test Horse"})
        ), patch.object(runner, "predict", return_value={}) as predict, patch.object(
            runner, "publish_engine_lock"
        ) as publish, patch.object(runner, "datetime", wraps=datetime) as clock:
            clock.now.return_value = start + timedelta(seconds=3)
            with self.assertRaisesRegex(ValueError, "prediction completed after off time"):
                runner.run(
                    self.card, {}, locked_at=(start - timedelta(hours=1)).isoformat(),
                    **self.kwargs
                )
            predict.assert_called_once()
            publish.assert_not_called()

    def test_publication_at_off_time_is_rejected(self):
        self.card["off_at"] = self.now.isoformat()
        self.invoke((self.now - timedelta(hours=1)).isoformat())


if __name__ == "__main__":
    unittest.main()
