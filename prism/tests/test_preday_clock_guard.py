import unittest
from datetime import datetime
from prism.preday_record_guard import validate_preday_record

BASE = dict(race_id='20261121_JRA_01_11', horse_id='h1', horse_name='テスト馬',
            forecaster_id='editor', source_id='official:test',
            saved_at='2026-11-20T10:00:00+09:00', version='preday-v1',
            scheduled_start_at='2026-11-21T15:00:00+09:00',
            source_authenticity_verified=True, record_type='preday_forecast')

class PredayClockTest(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(validate_preday_record(BASE, as_of='2026-11-20T11:00:00+09:00'))

    def test_future_rejected(self):
        with self.assertRaisesRegex(ValueError, 'future'):
            validate_preday_record(BASE, as_of='2026-11-20T09:00:00+09:00')

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError, 'timezone'):
            validate_preday_record(BASE, as_of=datetime(2026, 11, 20))

    def test_race_day_rejected(self):
        r = {**BASE, 'saved_at': '2026-11-21T09:00:00+09:00'}
        with self.assertRaisesRegex(ValueError, 'before race day'):
            validate_preday_record(r, as_of='2026-11-21T10:00:00+09:00')

if __name__ == '__main__':
    unittest.main()
