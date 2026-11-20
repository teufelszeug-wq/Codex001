"""Contract tests for batch preday forecast persistence; synthetic data only."""
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from preday_field_writer import save_preday_field

def sample(horse_id):
    return {
        "race_id": "20261121_TEST_01", "horse_id": horse_id,
        "horse_name": "架空馬" + horse_id, "forecaster_id": "editor",
        "source_id": "fixture", "saved_at": "2026-11-20T12:00:00+09:00",
        "version": "v1", "scheduled_start_at": "2026-11-21T15:00:00+09:00",
        "source_authenticity_verified": True, "record_type": "preday_forecast",
    }

class BatchWriterContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.as_of = datetime(2026, 11, 20, 13, tzinfo=timezone.utc)

    def test_two_horses_persist(self):
        paths = save_preday_field([sample("H1"), sample("H2")], self.root, as_of=self.as_of)
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(p.exists() for p in paths))

    def test_duplicate_identity_rejected_without_writes(self):
        with self.assertRaises(ValueError):
            save_preday_field([sample("H1"), sample("H1")], self.root, as_of=self.as_of)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_second_write_failure_rolls_back_first(self):
        from preday_field_writer import save_preday_record as real_save
        calls = 0
        def fail_second(record, path, *, as_of=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            return real_save(record, path, as_of=as_of)
        with patch("preday_field_writer.save_preday_record", side_effect=fail_second):
            with self.assertRaises(OSError):
                save_preday_field([sample("H1"), sample("H2")], self.root, as_of=self.as_of)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_file_not_overwritten(self):
        path = self.root / "20261121_TEST_01__editor__H1__v1.json"
        path.write_text("original")
        with self.assertRaises(FileExistsError):
            save_preday_field([sample("H1")], self.root, as_of=self.as_of)
        self.assertEqual(path.read_text(), "original")

if __name__ == "__main__":
    unittest.main()
