"""Synthetic-only regression for receipt-to-pipeline binding."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prism_engine.racecard_receipt import capture_racecard, save_receipt
from prism_engine.racecard_binding import verify_racecard_binding


class BindingTests(unittest.TestCase):
    def test_binding_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            card = {"race_id": "TEST-01", "runners": [
                {"horse_id": "a", "horse_name": "架空一号"},
                {"horse_id": "b", "horse_name": "架空二号"}]}
            path = root / "card.json"
            path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
            receipt = capture_racecard(path, source_url="https://example.org/test")
            receipt_path = save_receipt(receipt, root)
            payload = {"raw": {"race": {"race_id": "TEST-01"},
                                "runners": [{"horse_id": "a"}, {"horse_id": "b"}],
                                "source": {"source_id": receipt["sha256"]}},
                       "horse_names": {"a": "架空一号", "b": "架空二号"}}
            self.assertEqual(verify_racecard_binding(path, receipt_path, payload)["sha256"], receipt["sha256"])
            payload["horse_names"]["a"] = "改変"
            with self.assertRaisesRegex(ValueError, "horse names mismatch"):
                verify_racecard_binding(path, receipt_path, payload)
            payload["horse_names"]["a"] = "架空一号"
            path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_racecard_binding(path, receipt_path, payload)


if __name__ == "__main__":
    unittest.main()
