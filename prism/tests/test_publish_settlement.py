"""Regression cases for immutable post-race settlement publication."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publish_settlement import publish_settlement


class SettlementPublicationTests(unittest.TestCase):
    def test_idempotent_and_conflicting_result_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            forecast = root / "forecast.json"
            official = root / "official.json"
            forecast.write_text("{}", encoding="utf-8")
            official.write_text('{"result":1}', encoding="utf-8")
            summary = {"race_id": "20261116_TOKYO_11", "version": 1,
                       "forecasters": [], "forecast_sha256": "abc"}
            with patch("publish_settlement.settle_release", return_value=summary):
                first, created = publish_settlement(forecast, official, root / "out")
                self.assertTrue(created)
                second, created = publish_settlement(forecast, official, root / "out")
                self.assertFalse(created)
                self.assertEqual(first, second)
                self.assertEqual(json.loads(Path(first).read_text())["official_input_sha256"],
                                 __import__("hashlib").sha256(official.read_bytes()).hexdigest())
                official.write_text('{"result":2}', encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "conflicting settlement"):
                    publish_settlement(forecast, official, root / "out")

    def test_unsafe_race_path_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            forecast, official = root / "f", root / "o"
            forecast.write_text("{}")
            official.write_text("{}")
            with patch("publish_settlement.settle_release",
                       return_value={"race_id": "../escape", "version": 1}):
                with self.assertRaisesRegex(ValueError, "unsafe race_id"):
                    publish_settlement(forecast, official, root / "out")


if __name__ == "__main__":
    unittest.main()
