"""Contract tests for verified-field pipeline (synthetic fixtures only)."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from verified_field_pipeline import persist_verified_field


class VerifiedFieldPipelineTest(unittest.TestCase):
    def setUp(self):
        self.racecard = {
            "race_id": "TEST_20261121_01", "source_id": "fixture-only",
            "source_authenticity_verified": True,
            "scheduled_start_at": "2026-11-21T12:00:00+09:00",
            "horses": [
                {"horse_id": "h1", "horse_name": "架空馬甲"},
                {"horse_id": "h2", "horse_name": "架空馬乙"},
            ],
        }
        self.forecasts = [
            {"horse_id": "h1", "prediction": {"rank": 1}},
            {"horse_id": "h2", "prediction": {"rank": 2}},
        ]
        self.as_of = datetime.fromisoformat("2026-11-20T20:00:00+09:00")

    def test_complete_field_saved_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            args = dict(forecaster_id="test_model", version="v1", as_of=self.as_of)
            paths = persist_verified_field(self.racecard, self.forecasts, root, **args)
            self.assertEqual(len(paths), 2)
            self.assertTrue(all(Path(p).is_file() for p in paths))
            with self.assertRaises(FileExistsError):
                persist_verified_field(self.racecard, self.forecasts, root, **args)

    def test_missing_runner_creates_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                persist_verified_field(self.racecard, self.forecasts[:1], root,
                                       forecaster_id="test_model", version="v1", as_of=self.as_of)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_race_day_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                persist_verified_field(self.racecard, self.forecasts, root,
                                       forecaster_id="test_model", version="v1",
                                       as_of=datetime.fromisoformat("2026-11-21T08:00:00+09:00"))
            self.assertEqual(list(Path(root).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
