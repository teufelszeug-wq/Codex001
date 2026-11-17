import unittest
from snapshot_gate import validate_snapshot, settle_100yen

BASE = dict(
    race_id='TEST-20261118-01', horse_name='テスト馬', predictor_id='RIO',
    source='official', saved_at='2026-11-17T18:00:00+09:00',
    version='pre-v1', off_at='2026-11-18T12:00:00+09:00',
    kind='pre_race', evidence=[dict(
        available_at='2026-11-17T17:00:00+09:00',
        occurred_at='2026-11-16T12:00:00+09:00')])

class TestGate(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(validate_snapshot(BASE))
    def test_late(self):
        with self.assertRaisesRegex(ValueError, 'late'):
            validate_snapshot(dict(BASE, saved_at='2026-11-18T12:00:00+09:00'))
    def test_future(self):
        with self.assertRaisesRegex(ValueError, 'future'):
            validate_snapshot(dict(BASE, evidence=[dict(available_at='2026-11-17T19:00:00+09:00')]))
    def test_backdated(self):
        with self.assertRaisesRegex(ValueError, 'backdated'):
            validate_snapshot(dict(BASE, evidence=[dict(
                available_at='2026-11-17T16:00:00+09:00',
                observed_at='2026-11-17T17:00:00+09:00')]))
    def test_missing(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            validate_snapshot({k:v for k,v in BASE.items() if k != 'horse_name'})
    def test_timezone(self):
        with self.assertRaisesRegex(ValueError, 'timezone'):
            validate_snapshot(dict(BASE, saved_at='2026-11-17T18:00:00'))
    def test_unknown_kind(self):
        with self.assertRaisesRegex(ValueError, 'invalid snapshot kind'):
            validate_snapshot(dict(BASE, kind='other'))
    def test_premature_review(self):
        with self.assertRaisesRegex(ValueError, 'premature'):
            validate_snapshot(dict(BASE, kind='post_race_review'))
    def test_settlement(self):
        self.assertEqual(settle_100yen(2,340), dict(cost_yen=200,refund_yen=680,profit_yen=480))
    def test_zero(self):
        self.assertEqual(settle_100yen(1,0)['profit_yen'],-100)
    def test_invalid_units(self):
        with self.assertRaises(ValueError):
            settle_100yen(1.5,100)

if __name__ == '__main__':
    unittest.main()
