"""Isolated settlement bridge regression tests; all examples are fictional."""
import json
import tempfile
import unittest
from pathlib import Path
from settle_release import settle_release

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a = Path(self.tmp.name) / "forecast.json"
        self.b = Path(self.tmp.name) / "official.json"
        self.forecast = {"race_id":"TEST-01","version":1,"saved_at":"2026-11-15T18:00:00+09:00","off_at":"2026-11-16T15:00:00+09:00","records":[{"forecaster_id":"RIO","decision":"bet","bets":[{"horse_name":"架空馬","bet_type":"win","selection":"3","stake_yen":200}]}]}
        self.official = {"race_id":"TEST-01","status":"official","source_url":"https://example.org/official","payouts":[{"bet_type":"win","selection":"3","payout_yen_per_100":340}]}
    def run_case(self):
        self.a.write_text(json.dumps(self.forecast),encoding="utf8")
        self.b.write_text(json.dumps(self.official),encoding="utf8")
        return settle_release(self.a,self.b)
    def test_settlement(self):
        self.assertEqual(self.run_case()["forecasters"][0]["profit_yen"],480)
    def test_wrong_race(self):
        self.official["race_id"]="OTHER"
        with self.assertRaisesRegex(ValueError,"race_id"): self.run_case()
    def test_unverified(self):
        self.official["status"]="draft"
        with self.assertRaisesRegex(ValueError,"status"): self.run_case()
    def test_missing_selection(self):
        del self.forecast["records"][0]["bets"][0]["selection"]
        with self.assertRaisesRegex(ValueError,"selection"): self.run_case()
    def test_post_off(self):
        self.forecast["saved_at"]="2026-11-16T16:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"pre-off"): self.run_case()
    def test_duplicate_payout(self):
        self.official["payouts"]*=2
        with self.assertRaisesRegex(ValueError,"duplicate"): self.run_case()
    def test_abstain(self):
        self.forecast["records"][0]={"forecaster_id":"RIO","decision":"abstain"}
        self.assertEqual(self.run_case()["forecasters"][0]["stake_yen"],0)

if __name__=="__main__":
    unittest.main()
