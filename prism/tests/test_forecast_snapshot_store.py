import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from forecast_snapshot_store import save_snapshot

BASE = dict(race_id="20261123-JRA-TOKYO-11", forecaster_id="paper", horse_name="TEST",
            source="official", version="v1", status="pick", mark="◎", evidence_ids=["source-1"])
OFF = "2026-11-23T15:30:00+09:00"
BEFORE = datetime.fromisoformat("2026-11-22T12:00:00+09:00")
AFTER = datetime.fromisoformat("2026-11-23T16:00:00+09:00")

class TestStore(unittest.TestCase):
    def test_persists_actual_time(self):
        with tempfile.TemporaryDirectory() as root:
            p = save_snapshot(root, dict(BASE, saved_at="2000-01-01T00:00:00Z"), OFF, now=BEFORE)
            self.assertEqual(json.loads(p.read_text())["saved_at"], BEFORE.isoformat())
    def test_append_only(self):
        with tempfile.TemporaryDirectory() as root:
            p = save_snapshot(root, BASE, OFF, now=BEFORE)
            q = save_snapshot(root, BASE, OFF, now=BEFORE)
            self.assertNotEqual(p, q)
            self.assertEqual(len(list(p.parent.glob("*.json"))), 2)
    def test_postrace_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "pre-race"):
                save_snapshot(root, BASE, OFF, now=AFTER)
            self.assertEqual(list(Path(root).rglob("*.json")), [])
    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "unsafe race_id"):
                save_snapshot(root, dict(BASE, race_id="../bad"), OFF, now=BEFORE)
    def test_invalid_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "evidence IDs"):
                save_snapshot(root, dict(BASE, evidence_ids=[]), OFF, now=BEFORE)

if __name__ == "__main__":
    unittest.main()
