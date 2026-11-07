"""Fail-closed synthetic integration checks for verified settlement."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from prism_ops.verified_settlement import settle_verified_pre

class VerifiedSettlementTests(unittest.TestCase):
    def setUp(self):
        self.forecast={"race_id":"TEST-1","scheduled_off":"2026-11-07T10:00:00+09:00",
            "saved_at":"2026-11-07T09:00:00+09:00",
            "entries":[{"horse_no":1,"horse_name":"テスト馬"}],
            "required_agent_ids":["rio"],
            "agents":[{"agent_id":"rio","picks":[{"mark":"◎","horse_no":1}],
                       "tickets":[{"bet_type":"単勝","selection":[1],"stake_yen":100}]}],
            "editorial":{"picks":[{"mark":"◎","horse_no":1}],
                         "tickets":[{"bet_type":"単勝","selection":[1],"stake_yen":100}]}}
        self.now="2026-11-07T12:00:00+09:00"
    def test_no_receipt_no_settlement(self):
        r=settle_verified_pre(self.forecast,None,{"official_source":"official"},self.now)
        self.assertEqual(r["status"],"PRE_LOCK_FAILED")
        self.assertIsNone(r["by_agent"])
    def test_forged_boolean_not_enough(self):
        r=settle_verified_pre(self.forecast,{"external_timestamp_verified":True}, {"official_source":"official"},self.now)
        self.assertEqual(r["status"],"PRE_LOCK_FAILED")
    def test_missing_official_result(self):
        from prism_ops.forecast_completion_gate import digest
        receipt={"external_timestamp_verified":True,"immutable_location":"archive",
                 "trusted_saved_at":self.forecast["saved_at"],"readback_sha256":digest(self.forecast)}
        r=settle_verified_pre(self.forecast,receipt,None,self.now)
        self.assertEqual(r["status"],"RESULT_PENDING")
    def test_no_ticket_outcomes_not_loss(self):
        from prism_ops.forecast_completion_gate import digest
        receipt={"external_timestamp_verified":True,"immutable_location":"archive",
                 "trusted_saved_at":self.forecast["saved_at"],"readback_sha256":digest(self.forecast)}
        result={"race_id":"TEST-1","official_source":"official","retrieved_at":self.now}
        r=settle_verified_pre(self.forecast,receipt,result,self.now)
        self.assertEqual(r["status"],"SETTLEMENT_INCOMPLETE")
        self.assertIsNone(r["by_agent"])
if __name__=="__main__": unittest.main()
