"""Regression tests for the actual PRISM preday guard; run: python -m unittest discover -s prism/tests -p 'test_preday_guard_contract.py'"""
import unittest
from datetime import datetime, timezone
from prism.preday_record_guard import validate_preday_record

BASE = dict(race_id="JRA-20261121-TEST", horse_id="horse-001", horse_name="検証馬",
            forecaster_id="editor", source_id="official-source-sample",
            saved_at="2026-11-20T12:00:00+09:00", version="preday-v1",
            scheduled_start_at="2026-11-21T15:00:00+09:00",
            source_authenticity_verified=True, record_type="preday_forecast")
AS_OF = datetime(2026, 11, 20, 13, tzinfo=timezone.utc)

class PredayGuardContract(unittest.TestCase):
    def test_valid_preday_envelope(self):
        self.assertTrue(validate_preday_record(dict(BASE), as_of=AS_OF))
    def test_race_day_is_not_preday(self):
        r = dict(BASE, saved_at="2026-11-21T08:00:00+09:00")
        with self.assertRaises(ValueError):
            validate_preday_record(r, as_of="2026-11-21T09:00:00+09:00")
    def test_future_saved_at_rejected(self):
        r = dict(BASE, saved_at="2026-11-20T23:00:00+09:00")
        with self.assertRaises(ValueError):
            validate_preday_record(r, as_of="2026-11-20T12:00:00+09:00")
    def test_unverified_source_rejected(self):
        with self.assertRaises(ValueError):
            validate_preday_record(dict(BASE, source_authenticity_verified=False), as_of=AS_OF)
    def test_review_not_forecast(self):
        with self.assertRaises(ValueError):
            validate_preday_record(dict(BASE, record_type="postrace_review"), as_of=AS_OF)
    def test_naive_as_of_rejected(self):
        with self.assertRaises(ValueError):
            validate_preday_record(dict(BASE), as_of=datetime(2026, 11, 20, 13))
    def test_missing_forecaster_rejected(self):
        r = dict(BASE); del r["forecaster_id"]
        with self.assertRaises(ValueError):
            validate_preday_record(r, as_of=AS_OF)

if __name__ == "__main__":
    unittest.main()
