"""Regression tests for batch persistence boundary and append-only semantics."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from forecast_batch import persist_forecaster_batch


class BatchPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 24, 3, 0, tzinfo=timezone.utc)
        self.race = {"race_id": "test_race_001", "off_at": (self.now + timedelta(hours=2)).isoformat()}

    def test_empty_decisions_do_not_create_files(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                persist_forecaster_batch(root, self.race, [], now=self.now)
            self.assertEqual(list(Path(root).rglob("*.json")), [])

    def test_mismatched_race_does_not_create_files(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                persist_forecaster_batch(root, self.race, [{"race_id": "other"}], now=self.now)
            self.assertEqual(list(Path(root).rglob("*.json")), [])

    def test_naive_now_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                persist_forecaster_batch(root, self.race, [{}], now=self.now.replace(tzinfo=None))
            self.assertEqual(list(Path(root).rglob("*.json")), [])

    def test_write_failure_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("forecast_batch.save_snapshot", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    persist_forecaster_batch(root, self.race, [{"race_id": self.race["race_id"], "forecaster_id": "test", "horse_name": "test", "version": "v1"}], now=self.now)


if __name__ == "__main__":
    unittest.main()
