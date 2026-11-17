"""Regression tests for verified all-runner publication; synthetic fixtures only."""
import json
import tempfile
import unittest
from pathlib import Path
from prism.audit.verified_batch import publish_verified_batch

CARD = {
    "schema": "prism.official_racecard/v1", "source_verified": True,
    "race_id": "TEST-20261118-01", "off_at": "2026-11-18T12:00:00+09:00",
    "active_runners": [
        {"horse_id": "H1", "horse_name": "テスト馬甲"},
        {"horse_id": "H2", "horse_name": "テスト馬乙"},
    ],
}
EVIDENCE = [{"available_at": "2026-11-17T10:00:00+09:00"}]
PREDICTIONS = {
    "H1": {"horse_id": "H1", "horse_name": "テスト馬甲", "score": 0.7},
    "H2": {"horse_id": "H2", "horse_name": "テスト馬乙", "score": 0.3},
}

class VerifiedBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def publish(self, card=None, predictions=None, **overrides):
        kwargs = dict(predictor_id="paper", version="eve-v1",
                      source="synthetic-test", evidence=EVIDENCE,
                      saved_at="2026-11-17T11:00:00+09:00",
                      now="2026-11-17T11:01:00+09:00")
        kwargs.update(overrides)
        return publish_verified_batch(self.tmp.name, card or CARD,
                                      predictions if predictions is not None else PREDICTIONS, **kwargs)

    def test_complete_batch_and_append_only(self):
        path = self.publish()
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["snapshots"]), 2)
        self.assertEqual({r["horse_name"] for r in data["snapshots"]}, {"テスト馬甲", "テスト馬乙"})
        with self.assertRaises(FileExistsError):
            self.publish()
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.batch.json"))), 1)

    def test_swapped_names_rejected_without_publication(self):
        bad = {k: dict(v) for k, v in PREDICTIONS.items()}
        bad["H1"]["horse_name"] = "テスト馬乙"
        bad["H2"]["horse_name"] = "テスト馬甲"
        with self.assertRaises(ValueError):
            self.publish(predictions=bad)
        self.assertFalse(list(Path(self.tmp.name).iterdir()))

    def test_missing_runner_rejected(self):
        with self.assertRaises(ValueError):
            self.publish(predictions={"H1": PREDICTIONS["H1"]})
        self.assertFalse(list(Path(self.tmp.name).iterdir()))

    def test_future_evidence_rejected(self):
        with self.assertRaises(ValueError):
            self.publish(evidence=[{"available_at": "2026-11-17T12:00:00+09:00"}])
        self.assertFalse(list(Path(self.tmp.name).iterdir()))

    def test_after_off_rejected(self):
        with self.assertRaises(ValueError):
            self.publish(now="2026-11-18T12:00:00+09:00")
        self.assertFalse(list(Path(self.tmp.name).iterdir()))

if __name__ == "__main__":
    unittest.main()
