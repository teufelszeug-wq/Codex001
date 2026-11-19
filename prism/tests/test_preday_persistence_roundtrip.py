"""Synthetic persistence integration tests; no official racing data."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from prism_engine.preday_persistence import persist_prediction

class TestPreDayPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lock = {"race_id": "SYNTH-20261121-01", "cutoff": "2026-11-21T12:00:00+09:00", "lock_hash": "synthetic-hash", "win": {"h1": 0.6, "h2": 0.4}}
        self.runners = [{"horse_id": "h1", "horse_name": "架空馬甲"}, {"horse_id": "h2", "horse_name": "架空馬乙"}]

    def save(self, **overrides):
        kwargs = dict(lock=self.lock, runners=self.runners, predictor_id="synthetic-ai", source="synthetic-fixture", saved_at="2026-11-20T17:00:00+09:00", version="v1", output_dir=self.tmp.name)
        kwargs.update(overrides)
        return persist_prediction(**kwargs)

    def test_roundtrip_and_coverage(self):
        payload = json.loads(self.save().read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "prism.preday.saved/v1")
        self.assertEqual({r["horse_name"] for r in payload["records"]}, {"架空馬甲", "架空馬乙"})
        self.assertEqual(sum(r["win_probability"] for r in payload["records"]), 1)
        self.assertTrue(all(r["stage"] == "PRE_DAY" for r in payload["records"]))

    def test_existing_version_not_overwritten(self):
        path = self.save()
        before = path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.save()
        self.assertEqual(path.read_bytes(), before)

    def test_missing_runner_rejected_without_output(self):
        with self.assertRaises(ValueError):
            self.save(runners=self.runners[:1])
        self.assertEqual(list(Path(self.tmp.name).glob("*.json")), [])

    def test_duplicate_runner_rejected(self):
        with self.assertRaises(ValueError):
            self.save(runners=[self.runners[0], self.runners[0]])

    def test_non_normalized_probability_rejected(self):
        with self.assertRaises(ValueError):
            self.save(lock={**self.lock, "win": {"h1": 0.8, "h2": 0.8}})

    def test_same_day_cannot_be_preday(self):
        with self.assertRaises(ValueError):
            self.save(saved_at="2026-11-21T08:00:00+09:00")

    def test_post_cutoff_rejected(self):
        with self.assertRaises(ValueError):
            self.save(saved_at="2026-11-21T13:00:00+09:00")

if __name__ == "__main__":
    unittest.main()
