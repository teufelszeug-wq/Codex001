import unittest
from preday_record_guard import validate_preday_record

BASE = dict(race_id='JRA-20261121-TOKYO-11', horse_id='H001', horse_name='試験馬', forecaster_id='paper', source_id='official-test', saved_at='2026-11-20T23:59:59+09:00', version='preday-v1', scheduled_start_at='2026-11-21T15:30:00+09:00', source_authenticity_verified=True, record_type='preday_forecast')
class GuardTest(unittest.TestCase):
    def test_previous_day(self):
        self.assertTrue(validate_preday_record(BASE))
    def test_same_day_rejected(self):
        with self.assertRaisesRegex(ValueError, 'before race day'):
            validate_preday_record({**BASE, 'saved_at':'2026-11-21T00:00:00+09:00'})
    def test_utc_boundary_rejected(self):
        with self.assertRaisesRegex(ValueError, 'before race day'):
            validate_preday_record({**BASE, 'saved_at':'2026-11-20T15:00:00Z'})
    def test_unverified_rejected(self):
        with self.assertRaisesRegex(ValueError, 'official source'):
            validate_preday_record({**BASE, 'source_authenticity_verified':False})
    def test_after_start_rejected(self):
        with self.assertRaisesRegex(ValueError, 'precede scheduled start'):
            validate_preday_record({**BASE, 'saved_at':'2026-11-21T15:30:00+09:00'})
    def test_naive_rejected(self):
        with self.assertRaisesRegex(ValueError, 'timezone required'):
            validate_preday_record({**BASE, 'saved_at':'2026-11-20T12:00:00'})
if __name__ == '__main__': unittest.main()
