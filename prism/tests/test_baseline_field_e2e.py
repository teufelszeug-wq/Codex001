"""End-to-end baseline -> bridge -> immutable JSON regression tests.

Uses synthetic fixtures only; never counts as an official race forecast.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from baseline_field_pipeline import persist_baseline_field


class BaselineFieldEndToEnd(unittest.TestCase):
    def setUp(self):
        self.start = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=6, minute=0, second=0, microsecond=0)
        self.cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.card = {
            "race_id": "TEST20261121R01", "source_id": "synthetic_test_only",
            "source_authenticity_verified": True,
            "scheduled_start_at": self.start.isoformat(),
            "horses": [{"horse_id": "H001", "horse_name": "架空一号"},
                       {"horse_id": "H002", "horse_name": "架空二号"}],
        }
        self.features = [
            {"horse_id": "H001", "observed_at": self.cutoff.isoformat(), "pre_race_score": 1.0},
            {"horse_id": "H002", "observed_at": self.cutoff.isoformat(), "pre_race_score": 0.0},
        ]

    def test_end_to_end_and_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = persist_baseline_field(self.card, self.features, directory, cutoff_at=self.cutoff.isoformat())
            self.assertEqual(len(paths), 2)
            records = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
            self.assertEqual({r["horse_name"] for r in records}, {"架空一号", "架空二号"})
            self.assertAlmostEqual(sum(r["prediction"]["win_probability"] for r in records), 1.0)
            with self.assertRaises(FileExistsError):
                persist_baseline_field(self.card, self.features, directory, cutoff_at=self.cutoff.isoformat())
            self.assertEqual(len(list(Path(directory).glob("*.json"))), 2)

    def test_post_cutoff_feature_rejected_without_files(self):
        with tempfile.TemporaryDirectory() as directory:
            self.features[0]["observed_at"] = datetime.now(timezone.utc).isoformat()
            with self.assertRaises(ValueError):
                persist_baseline_field(self.card, self.features, directory, cutoff_at=self.cutoff.isoformat())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_missing_runner_rejected_without_files(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                persist_baseline_field(self.card, self.features[:1], directory, cutoff_at=self.cutoff.isoformat())
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
