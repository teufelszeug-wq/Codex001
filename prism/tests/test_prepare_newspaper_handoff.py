"""Tests for the newspaper handoff adapter using real file I/O."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("prepare_newspaper_handoff", SCRIPTS / "prepare_newspaper_handoff.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class HandoffAdapterTest(unittest.TestCase):
    def test_missing_history_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(FileNotFoundError):
                adapter.prepare(root, "20261123-JRA-TOKYO-11", root / "handoff.json")

    def test_no_final_forecast_is_blocked_and_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            race_id = "20261123-JRA-TOKYO-11"
            folder = root / race_id
            folder.mkdir()
            card = {
                "race_id": race_id,
                "off_at": "2026-11-23T15:30:00+09:00",
                "runners": [{"horse_no": 1, "horse_name": "TEST HORSE", "status": "RUNNING"}],
            }
            (folder / "racecard.json").write_text(json.dumps(card), encoding="utf-8")
            output = root / "handoff.json"
            result = adapter.prepare(root, race_id, output)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("NO_FINAL_FORECAST", result["blocking_reasons"])
            self.assertIn("NO_SAVED_ROUNDTABLE", result["blocking_reasons"])
            self.assertTrue(output.is_file())
            self.assertFalse(result["paper_generated"])


if __name__ == "__main__":
    unittest.main()
