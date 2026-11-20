import unittest
from datetime import datetime, timezone

from prism.preday_record_guard import validate_preday_record


class TestAsOfTypes(unittest.TestCase):
    def setUp(self):
        self.record = {
            'race_id': 'TEST-20261121-01', 'horse_id': 'TEST-H01',
            'horse_name': 'テスト馬', 'forecaster_id': 'TEST-AI',
            'source_id': 'TEST-SOURCE', 'saved_at': '2026-11-20T10:00:00+09:00',
            'version': 'preday-v1', 'scheduled_start_at': '2026-11-21T15:00:00+09:00',
            'source_authenticity_verified': True, 'record_type': 'preday_forecast'
        }

    def test_invalid_as_of_types_rejected(self):
        for value in (0, False, [], {}, 123.5):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'as_of must'):
                validate_preday_record(self.record, as_of=value)

    def test_aware_as_of_accepted(self):
        self.assertTrue(validate_preday_record(self.record, as_of=datetime(2026, 11, 20, 12, tzinfo=timezone.utc)))

    def test_naive_as_of_rejected(self):
        with self.assertRaisesRegex(ValueError, 'timezone'):
            validate_preday_record(self.record, as_of=datetime(2026, 11, 20, 12))


if __name__ == '__main__':
    unittest.main()
