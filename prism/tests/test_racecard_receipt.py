"""Regression tests for racecard capture receipts (synthetic fixtures only)."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prism_engine.racecard_receipt import capture_racecard, save_receipt


class RacecardReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "racecard.json"
        self.card = {"race_id": "TEST-20261121-01", "runners": [
            {"horse_id": "h1", "horse_name": "架空一号"},
            {"horse_id": "h2", "horse_name": "架空二号"},
        ]}
        self.write_card()

    def write_card(self):
        self.path.write_text(json.dumps(self.card, ensure_ascii=False), encoding="utf-8")

    def test_digest_and_immutable_receipt(self):
        receipt = capture_racecard(self.path, source_url="https://example.org/test",
                                   captured_at="2026-11-20T06:00:00+09:00")
        self.assertEqual(receipt["sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(receipt["runner_count"], 2)
        self.assertIs(receipt["source_authenticity_verified"], False)
        stored = save_receipt(receipt, Path(self.tmp.name) / "receipts")
        self.assertEqual(json.loads(stored.read_text(encoding="utf-8")), receipt)
        with self.assertRaises(FileExistsError):
            save_receipt(receipt, stored.parent)

    def test_duplicate_horse_id_rejected(self):
        self.card["runners"][1]["horse_id"] = "h1"
        self.write_card()
        with self.assertRaisesRegex(ValueError, "duplicate horse_id"):
            capture_racecard(self.path, source_url="https://example.org/test")

    def test_naive_capture_time_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone aware"):
            capture_racecard(self.path, source_url="https://example.org/test",
                             captured_at="2026-11-20T06:00:00")

    def test_missing_horse_name_rejected(self):
        self.card["runners"][0]["horse_name"] = ""
        self.write_card()
        with self.assertRaisesRegex(ValueError, "horse_name"):
            capture_racecard(self.path, source_url="https://example.org/test")


if __name__ == "__main__":
    unittest.main()
