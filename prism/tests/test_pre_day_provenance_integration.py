"""Regression tests for the actual provenance validator; synthetic records only."""
import unittest
from prism_engine.pre_day_record import validate

BASE = dict(race_id='SYNTH-20261120-01', horse_id='SYNTH-A', horse_name='架空馬A',
            predictor_id='EDITOR', source='SYNTHETIC', saved_at='2026-11-19T20:00:00+09:00',
            version='v1', cutoff='2026-11-20T15:00:00+09:00', stage='PRE_DAY',
            source_available_at='2026-11-19T19:00:00+09:00')

class ProvenanceIntegration(unittest.TestCase):
    def test_pre_day(self): self.assertEqual(validate(BASE)['stage'], 'PRE_DAY')
    def test_day_delta(self):
        r=dict(BASE,saved_at='2026-11-20T10:00:00+09:00',stage='DAY_DELTA')
        self.assertEqual(validate(r)['stage'],'DAY_DELTA')
    def test_pre_day_mislabeled(self):
        with self.assertRaisesRegex(ValueError,'PRE_DAY must'):
            validate(dict(BASE,saved_at='2026-11-20T10:00:00+09:00'))
    def test_day_delta_mislabeled(self):
        with self.assertRaisesRegex(ValueError,'DAY_DELTA must'): validate(dict(BASE,stage='DAY_DELTA'))
    def test_future_source(self):
        with self.assertRaisesRegex(ValueError,'source unavailable'):
            validate(dict(BASE,source_available_at='2026-11-20T10:00:00+09:00'))
    def test_after_cutoff(self):
        with self.assertRaisesRegex(ValueError,'at or after cutoff'):
            validate(dict(BASE,saved_at='2026-11-20T15:00:00+09:00'))
    def test_naive_time(self):
        with self.assertRaisesRegex(ValueError,'naive timestamp'):
            validate(dict(BASE,saved_at='2026-11-19T20:00:00'))
    def test_missing_horse_name(self):
        with self.assertRaisesRegex(ValueError,'missing required'): validate(dict(BASE,horse_name=''))
    def test_post_race(self):
        r=dict(BASE,stage='POST_RACE',saved_at='2026-11-20T16:00:00+09:00')
        self.assertEqual(validate(r)['stage'],'POST_RACE')

if __name__=='__main__': unittest.main()
