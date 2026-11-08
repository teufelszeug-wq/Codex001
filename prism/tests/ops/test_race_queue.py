import unittest
from unittest.mock import patch
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))
from prism_ops.race_queue import next_work,snapshot_gate

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.r={"race_id":"JRA-20261107-TOKYO-11","input_sha256":"abc",
            "scheduled_off":"2026-11-07T15:35:00+09:00","official_entries_verified":True}
    def test_eligible(self):
        self.assertEqual(len(next_work([self.r],"2026-11-06T23:00:00+09:00")["eligible"]),1)
    def test_late(self):
        self.assertEqual(next_work([self.r],"2026-11-07T16:00:00+09:00")["blocked"][0]["reason"],"NO_PRE_WINDOW")
    def test_missing_official(self):
        self.assertEqual(next_work([{**self.r,"official_entries_verified":False}],"2026-11-06T23:00:00+09:00")["blocked"][0]["reason"],"OFFICIAL_DATA_MISSING")
    def test_deduplicate(self):
        self.assertEqual(len(next_work([self.r,self.r],"2026-11-06T23:00:00+09:00")["eligible"]),1)
    def test_exposed(self):
        self.assertEqual(next_work([{**self.r,"result_exposed":True}],"2026-11-06T23:00:00+09:00")["blocked"][0]["reason"],"NO_PRE_WINDOW")
    def test_receipt_missing(self):
        f={"race_id":"test","saved_at":"2026-11-06T23:00:00+09:00","scheduled_off":"2026-11-07T15:35:00+09:00","entries":[{"horse_no":1,"horse_name":"架空"}],"agents":[{"agent_id":"rio","picks":[{"horse_no":1,"mark":"◎"}],"tickets":[{"bet_type":"単勝","selection":[1],"stake_yen":100}]}],"editorial":{"picks":[{"horse_no":1,"mark":"◎"}],"pass_reason":"見送り"}}
        self.assertIn("PERSISTENCE_READBACK_FAILED",snapshot_gate(f,None,"2026-11-06T23:00:00+09:00")["errors"])
    def test_verified_pre_survives_post_race_audit(self):
        from prism_ops.forecast_completion_gate import digest
        f={"race_id":"synthetic","saved_at":"2026-11-07T09:00:00+09:00",
           "scheduled_off":"2026-11-07T10:00:00+09:00",
           "entries":[{"horse_no":1,"horse_name":"架空"}],
           "required_agent_ids":["rio"],
           "agents":[{"agent_id":"rio","picks":[{"horse_no":1,"mark":"◎"}],
                      "tickets":[{"bet_type":"単勝","selection":[1],"stake_yen":100}]}],
           "editorial":{"picks":[{"horse_no":1,"mark":"◎"}],"pass_reason":"見送り"}}
        receipt={"forecast_sha256":digest(f),"timestamp_verified":True,
                 "immutable_location":"synthetic://receipt",
                 "trusted_saved_at":"2026-11-07T09:00:00+09:00"}
        # Isolated trusted-clock test: proof verification itself is covered by
        # the strict M4 integration tests, not by this synthetic receipt.
        with patch("prism_ops.forecast_completion_gate.validate_forecast",
                   return_value={"complete": True, "errors": [], "sha256":digest(f)}):
            self.assertTrue(snapshot_gate(f,receipt,"2026-11-07T11:00:00+09:00")["verified_pre"])
            late={**receipt,"trusted_saved_at":"2026-11-07T10:01:00+09:00"}
            self.assertIn("TRUSTED_TIMESTAMP_AFTER_OFF",
                          snapshot_gate(f,late,"2026-11-07T11:00:00+09:00")["errors"])
if __name__=="__main__":unittest.main()
