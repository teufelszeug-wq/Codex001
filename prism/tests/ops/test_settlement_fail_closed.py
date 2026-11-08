"""Synthetic tests for fail-closed settlement; no real racing data."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "prism_ops"))
from settlement_fail_closed import settle_ticket_outcomes

T = [{"bet_type": "単勝", "selection": [1], "stake_yen": 100}]

class TestSettlement(unittest.TestCase):
    def test_win(self):
        self.assertEqual(settle_ticket_outcomes(T, {"単勝:1": {"status":"won","payout_yen":320}})["roi_pct_ex_refund"], 320)
    def test_loss(self):
        self.assertEqual(settle_ticket_outcomes(T, {"単勝:1": {"status":"lost","payout_yen":0}})["net_yen"], -100)
    def test_refund(self):
        self.assertIsNone(settle_ticket_outcomes(T, {"単勝:1": {"status":"refunded","payout_yen":100}})["roi_pct_ex_refund"])
    def test_missing_is_not_loss(self):
        with self.assertRaisesRegex(ValueError, "UNADJUDICATED"): settle_ticket_outcomes(T, {})
    def test_contradictory(self):
        with self.assertRaisesRegex(ValueError, "INCONSISTENT"): settle_ticket_outcomes(T, {"単勝:1": {"status":"lost","payout_yen":320}})
    def test_stake(self):
        with self.assertRaisesRegex(ValueError, "STAKE"): settle_ticket_outcomes([{**T[0],"stake_yen":200}], {})
    def test_pass(self):
        self.assertIsNone(settle_ticket_outcomes([], {})["roi_pct_ex_refund"])

if __name__ == "__main__": unittest.main()
