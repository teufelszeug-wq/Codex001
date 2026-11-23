"""Regression tests for partial-write rollback in the batch adapter."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import forecast_batch


class BatchRollbackTests(unittest.TestCase):
    def test_second_write_failure_removes_first_snapshot(self):
        now = datetime(2026, 11, 23, 8, 0, tzinfo=timezone.utc)
        off_at = (now + timedelta(hours=2)).isoformat()
        race = {"race_id": "20261123_TOKYO_11", "off_at": off_at}
        decisions = [
            {"race_id": race["race_id"], "forecaster_id": f"forecaster_{i}",
             "horse_name": f"horse_{i}", "source": "test_fixture",
             "version": "v1", "status": "pass"}
            for i in range(2)
        ]
        original = forecast_batch.save_snapshot
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected disk failure")
            return original(*args, **kwargs)

        with tempfile.TemporaryDirectory() as root:
            with patch.object(forecast_batch, "save_snapshot", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "injected disk failure"):
                    forecast_batch.persist_forecaster_batch(root, race, decisions, now=now)
            self.assertEqual(list(Path(root).rglob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
