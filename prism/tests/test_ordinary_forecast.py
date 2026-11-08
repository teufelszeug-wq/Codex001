"""Ordinary PRE must remain usable editorially without pretending Golden proof."""
import hashlib
import json
import unittest
from prism_ops.ordinary_forecast import assess_ordinary_forecast

class OrdinaryForecastTests(unittest.TestCase):
    def setUp(self):
        inp = {"official_source": "TEST_ONLY"}
        digest = hashlib.sha256(json.dumps(inp, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.data = {
            "race_id": "TEST-R1", "forecast_version": "v1", "input_hash": digest,
            "input_snapshot": inp, "saved_at": "2026-11-08T17:00:00+09:00",
            "source_as_of": "2026-11-08T16:55:00+09:00",
            "scheduled_off": "2026-11-08T18:15:00+09:00",
            "results_exposed": False,
            "entries": [{"horse_no": 1, "horse_name": "テスト馬"}],
            "required_agent_ids": ["RIO"],
            "agents": [{"agent_id": "RIO",
                        "picks": [{"horse_no": 1, "horse_name": "テスト馬", "mark": "◎"}],
                        "tickets": [{"bet_type": "単勝", "selection": [1], "stake_yen": 100}]}],
            "editorial": {"picks": [{"horse_no": 1, "horse_name": "テスト馬", "mark": "◎"}],
                          "tickets": [{"bet_type": "単勝", "selection": [1], "stake_yen": 100}]}
        }

    def check(self, expected, now="2026-11-08T17:05:00+09:00"):
        result = assess_ordinary_forecast(self.data, observed_at=now)
        self.assertEqual(result["usable"], expected, result)
        self.assertFalse(result["eligible_for_golden_roi"])
        return result

    def test_ordinary_without_rfc3161_is_editorial_usable(self):
        result = self.check(True)
        self.assertEqual(result["status"], "UNVERIFIED_PRE_FORECAST")
        self.assertTrue(result["eligible_for_editorial"])

    def test_after_off_cannot_create_pre(self):
        self.assertIn("PRE_WINDOW_CLOSED", self.check(False, "2026-11-08T18:16:00+09:00")["errors"])

    def test_result_exposure_rejected(self):
        self.data["results_exposed"] = True
        self.assertIn("RESULT_EXPOSURE_NOT_EXCLUDED", self.check(False)["errors"])

    def test_agent_coverage_rejected(self):
        self.data["required_agent_ids"].append("OTHER")
        self.assertIn("AGENT_COVERAGE_INCOMPLETE", self.check(False)["errors"])

    def test_ticket_stake_rejected(self):
        self.data["agents"][0]["tickets"][0]["stake_yen"] = 200
        self.assertIn("RIO:INVALID_TICKET", self.check(False)["errors"])

    def test_input_hash_rejected(self):
        self.data["input_snapshot"]["official_source"] = "TAMPERED"
        self.assertIn("INPUT_HASH_MISMATCH", self.check(False)["errors"])

    def test_future_saved_at_rejected(self):
        self.assertIn("FUTURE_SAVED_AT", self.check(False, "2026-11-08T16:59:00+09:00")["errors"])

    def test_missing_editorial_rejected(self):
        self.data.pop("editorial")
        self.assertIn("EDITORIAL_MISSING", self.check(False)["errors"])

if __name__ == "__main__":
    unittest.main()
