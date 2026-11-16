"""Regression checks for locked live publication deadline."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from forecast_release import release


class LiveDeadlineTests(unittest.TestCase):
    def test_expired_deadline_does_not_write_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.json"
            source.write_text(json.dumps({"race_id": "TEST_001", "version": 1}), encoding="utf-8")
            out = Path(tmp) / "out"
            with patch("forecast_release.validate", return_value=[]):
                with self.assertRaisesRegex(ValueError, "deadline passed"):
                    release(source, out, live_off_at=datetime.now(timezone.utc) - timedelta(seconds=1))
            self.assertEqual(list(out.rglob("v*.json")), [])

    def test_future_deadline_allows_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.json"
            source.write_text(json.dumps({"race_id": "TEST_001", "version": 1}), encoding="utf-8")
            with patch("forecast_release.validate", return_value=[]):
                path, digest, created = release(
                    source, Path(tmp) / "out",
                    live_off_at=datetime.now(timezone.utc) + timedelta(hours=1))
            self.assertTrue(created)
            self.assertTrue(Path(path).is_file())
            self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
