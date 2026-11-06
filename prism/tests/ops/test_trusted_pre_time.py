"""Regression checks for timestamp-trust PRE lock gate (synthetic only)."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from prism_ops.race_queue import snapshot_gate
from prism_ops.forecast_completion_gate import digest

def sample(saved="2026-11-07T10:00:00+09:00"):
    return {"race_id":"SYNTH","saved_at":saved,"scheduled_off":"2026-11-07T15:35:00+09:00",
            "entries":[{"horse_no":1,"horse_name":"架空馬"}],
            "agents":[{"agent_id":"rio","picks":[{"horse_no":1,"mark":"◎"}],
                       "tickets":[{"bet_type":"単勝","selection":[1],"stake_yen":100}]}],
            "editorial":{"picks":[{"horse_no":1,"mark":"◎"}],"pass_reason":"見送り"}}

def receipt(f, trusted=None):
    return {"readback_sha256":digest(f),"external_timestamp_verified":True,
            "immutable_location":"test://fixture",
            "trusted_saved_at":trusted}

class TrustedTimeTests(unittest.TestCase):
    def test_valid_synthetic_receipt(self):
        f=sample()
        self.assertTrue(snapshot_gate(f,receipt(f,f["saved_at"]),"2026-11-07T11:00:00+09:00")["verified_pre"])
    def test_future_saved_at(self):
        f=sample("2026-11-07T12:00:00+09:00")
        self.assertIn("FUTURE_SAVED_AT",snapshot_gate(f,receipt(f,f["saved_at"]),"2026-11-07T11:00:00+09:00")["errors"])
    def test_missing_trusted_timestamp(self):
        f=sample()
        self.assertIn("TRUSTED_TIMESTAMP_MISSING",snapshot_gate(f,receipt(f),"2026-11-07T11:00:00+09:00")["errors"])
    def test_future_trusted_timestamp(self):
        f=sample()
        self.assertIn("FUTURE_TRUSTED_TIMESTAMP",snapshot_gate(f,receipt(f,"2026-11-07T12:00:00+09:00"),"2026-11-07T11:00:00+09:00")["errors"])
    def test_trusted_timestamp_after_off(self):
        f=sample()
        self.assertIn("TRUSTED_TIMESTAMP_AFTER_OFF",snapshot_gate(f,receipt(f,"2026-11-07T16:00:00+09:00"),"2026-11-07T11:00:00+09:00")["errors"])

if __name__=="__main__": unittest.main()
