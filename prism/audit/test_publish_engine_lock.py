"""Contract tests for engine-lock -> verified pre-race batch publication."""
import json
import tempfile
import unittest
from pathlib import Path
from prism.audit.publish_engine_lock import publish_engine_lock

CARD = {
    "schema": "prism.official_racecard/v1", "source_verified": True,
    "race_id": "TEST-2026-11-21-01", "off_at": "2026-11-21T15:00:00+09:00",
    "active_runners": [
        {"horse_id": "h1", "horse_name": "架空馬甲"},
        {"horse_id": "h2", "horse_name": "架空馬乙"},
    ],
}
LOCK = {
    "schema": "prism.engine.prediction/v1",
    "race_id": CARD["race_id"], "cutoff": CARD["off_at"],
    "win": {"h1": 0.6, "h2": 0.4},
    "scores": {"h1": 72.0, "h2": 69.0},
    "lock_hash": "synthetic-lock", "input_hash": "synthetic-input",
    "model_version": "synthetic-test",
}
KW = {
    "predictor_id": "synthetic-engine", "version": "test-v1",
    "source": "synthetic-contract-test",
    "evidence": [{"available_at": "2026-11-20T10:00:00+09:00"}],
    "saved_at": "2026-11-20T12:00:00+09:00",
    "now": "2026-11-20T12:01:00+09:00",
}

class EnginePublicationTest(unittest.TestCase):
    def test_publish_full_field_and_reject_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            target = publish_engine_lock(d, CARD, LOCK, **KW)
            rows = json.loads(Path(target).read_text(encoding="utf-8"))["snapshots"]
            self.assertEqual({r["horse_name"] for r in rows}, {"架空馬甲", "架空馬乙"})
            self.assertTrue(all(r["kind"] == "pre_race" for r in rows))
            with self.assertRaises(FileExistsError):
                publish_engine_lock(d, CARD, LOCK, **KW)

    def test_incomplete_engine_lock_cannot_publish(self):
        with tempfile.TemporaryDirectory() as d:
            broken = dict(LOCK, win={"h1": 1.0})
            with self.assertRaises(ValueError):
                publish_engine_lock(d, CARD, broken, **KW)
            self.assertEqual(list(Path(d).glob("*.batch.json")), [])

    def test_future_evidence_cannot_publish(self):
        with tempfile.TemporaryDirectory() as d:
            bad = dict(KW, evidence=[{"available_at": "2026-11-20T13:00:00+09:00"}])
            with self.assertRaises(ValueError):
                publish_engine_lock(d, CARD, LOCK, **bad)
            self.assertEqual(list(Path(d).glob("*.batch.json")), [])

    def test_after_off_cannot_publish(self):
        with tempfile.TemporaryDirectory() as d:
            bad = dict(KW, now="2026-11-21T15:01:00+09:00")
            with self.assertRaises(ValueError):
                publish_engine_lock(d, CARD, LOCK, **bad)

if __name__ == "__main__":
    unittest.main()
