"""Append-only preday persistence regression tests."""
import json
import tempfile
import unittest
from pathlib import Path
from prism.preday_batch_store import persist_preday_batch

def record(hid="h1"):
    return dict(race_id="20261122-TOK-11", horse_id=hid, horse_name="試験馬",
        forecaster_id="editorial", source_id="fixture", saved_at="2026-11-21T10:00:00+09:00",
        version="preday-v1", record_type="preday_forecast",
        source_authenticity_verified=True, prediction={"win_probability": 1.0})

class BatchStoreTests(unittest.TestCase):
    def test_write_and_preserve_japanese(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(persist_preday_batch([record()], d))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))[0]["horse_name"], "試験馬")
            with self.assertRaises(FileExistsError):
                persist_preday_batch([record()], d)
            self.assertEqual(len(list(Path(d).glob("*.json"))), 1)

    def test_reject_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            r = record()
            r["source_authenticity_verified"] = False
            with self.assertRaises(ValueError):
                persist_preday_batch([r], d)

    def test_reject_mixed_batch(self):
        with tempfile.TemporaryDirectory() as d:
            r = record("h2")
            r["version"] = "preday-v2"
            with self.assertRaises(ValueError):
                persist_preday_batch([record(), r], d)

    def test_reject_unsafe_id(self):
        with tempfile.TemporaryDirectory() as d:
            r = record()
            r["race_id"] = "../escape"
            with self.assertRaises(ValueError):
                persist_preday_batch([r], d)

    def test_reject_duplicate_horse(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                persist_preday_batch([record(), record()], d)

if __name__ == "__main__":
    unittest.main()
