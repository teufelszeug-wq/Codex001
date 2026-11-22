"""Regression coverage for official horse-number normalization before gate validation."""
import unittest
from unittest.mock import patch
from prism.scripts import run_verified_pre_day as runner


class OfficialNumberNormalizationTests(unittest.TestCase):
    def test_numeric_string_normalizes_before_gate(self):
        card = {"off_at": "2099-01-01T12:00:00+00:00",
                "active_runners": [{"horse_id": "H1", "horse_name": "Horse 1",
                                    "horse_no": "7", "horse_number": "7"}]}
        with patch.object(runner, "validate_engine_input", side_effect=ValueError("gate reached")) as gate:
            with self.assertRaisesRegex(ValueError, "gate reached"):
                runner.run(card, {}, venue="TEST", surface="turf", distance_m=1600,
                           direction="right", class_rating=1, barrier_count=8,
                           locked_at="2026-11-18T00:00:00+00:00", output_dir="/tmp/test",
                           predictor_id="test", version="test", source="test",
                           source_evidence=[{"source_url": "https://example.invalid/synthetic-test", "retrieved_at": "2026-11-18T00:00:00+00:00"}])
            normalized = gate.call_args.args[0]["active_runners"][0]
            self.assertEqual(normalized["horse_number"], 7)
            self.assertEqual(normalized["horse_no"], 7)

    def test_bool_number_is_rejected_before_gate(self):
        card = {"active_runners": [{"horse_id": "H1", "horse_no": True, "horse_number": 1}]}
        with patch.object(runner, "validate_engine_input") as gate:
            with self.assertRaisesRegex(ValueError, "positive canonical integer"):
                runner.run(card, {}, venue="TEST", surface="turf", distance_m=1600,
                           direction="right", class_rating=1, barrier_count=8,
                           locked_at="2026-11-18T00:00:00+00:00", output_dir="/tmp/test",
                           predictor_id="test", version="test", source="test",
                           source_evidence=[{"source_url": "https://example.invalid/synthetic-test", "retrieved_at": "2026-11-18T00:00:00+00:00"}])
            gate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
