import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from settlement_100yen import settle

class SettlementTests(unittest.TestCase):
    def test_win_loss(self):
        self.assertEqual(settle([{'bet_type':'単勝','selection':'3','stake_yen':200},{'bet_type':'単勝','selection':'5','stake_yen':100}],{('単勝','3'):340})['profit_yen'],380)
    def test_abstain(self):
        self.assertEqual(settle([],{})['profit_yen'],0)
    def test_reject_non_hundred(self):
        with self.assertRaises(ValueError): settle([{'bet_type':'単勝','selection':'3','stake_yen':150}],{})
    def test_reject_bool(self):
        with self.assertRaises(ValueError): settle([{'bet_type':'単勝','selection':'3','stake_yen':True}],{})
    def test_reject_bad_payout(self):
        with self.assertRaises(ValueError): settle([{'bet_type':'単勝','selection':'3','stake_yen':100}],{('単勝','3'):-1})

if __name__ == '__main__': unittest.main()
