"""Actual predict() -> immutable pre-day JSON integration, synthetic only."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from prism_engine.engine import predict
from prism_engine.preday_persistence import persist_prediction
from test_engine_full_synthetic_smoke import fixture, LOCK

class PredictToPersistence(unittest.TestCase):
    def test_engine_output_roundtrip(self):
        raw = fixture()
        lock = predict(raw, LOCK)
        runners = [
            {"horse_id": runner["horse_id"], "horse_name": "架空馬" + str(i)}
            for i, runner in enumerate(raw["runners"], 1)
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = persist_prediction(
                lock, runners, predictor_id="synthetic-engine",
                source="SYNTHETIC-TEST-ONLY", saved_at=LOCK,
                version="v1", output_dir=directory)
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["records"]), len(raw["runners"]))
            self.assertEqual(
                {r["horse_id"]: r["win_probability"] for r in saved["records"]},
                lock["win"])
            self.assertEqual(
                {r["prediction_hash"] for r in saved["records"]},
                {lock["lock_hash"]})
            self.assertEqual({r["stage"] for r in saved["records"]}, {"PRE_DAY"})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                persist_prediction(
                    lock, runners, predictor_id="synthetic-engine",
                    source="SYNTHETIC-TEST-ONLY", saved_at=LOCK,
                    version="v1", output_dir=directory)
            self.assertEqual(path.read_bytes(), before)

    def test_missing_runner_does_not_create_file(self):
        raw = fixture()
        lock = predict(raw, LOCK)
        runners = [{"horse_id": raw["runners"][0]["horse_id"], "horse_name": "架空馬1"}]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "runner coverage mismatch"):
                persist_prediction(lock, runners, predictor_id="synthetic-engine",
                                   source="SYNTHETIC-TEST-ONLY", saved_at=LOCK,
                                   version="v1", output_dir=directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

if __name__ == "__main__":
    unittest.main()
