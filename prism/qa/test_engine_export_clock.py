"""Clock regression for engine export. Run: python -m unittest prism/qa/test_engine_export_clock.py"""
import unittest
from datetime import datetime, timezone
from prism.qa.engine_prediction_export import export_engine_predictions

class EngineExportClockTests(unittest.TestCase):
    def setUp(self):
        self.artifact = {
            'schema': 'prism.engine.prediction/v1',
            'mode': 'PRE_AVAILABLE',
            'source_authenticity_verified': True,
            'race_id': 'fixture-race',
            'locked_at': '2026-11-14T10:00:00+09:00',
            'cutoff': '2026-11-14T10:00:00+09:00',
            'win': {'h1': 0.6, 'h2': 0.4},
        }
        self.kwargs = dict(horses={'h1': 'Horse One', 'h2': 'Horse Two'},
            predictor_id='fixture-predictor', source='fixture-source',
            version='pre-v1', scheduled_start_at='2026-11-15T15:00:00+09:00',
            now='2026-11-14T11:00:00+09:00')

    def test_future_saved_at_rejected(self):
        with self.assertRaisesRegex(ValueError, 'future_saved_at'):
            export_engine_predictions(self.artifact,
                saved_at='2026-11-14T12:00:00+09:00', **self.kwargs)

    def test_equal_to_actual_now_allowed(self):
        result = export_engine_predictions(self.artifact,
            saved_at='2026-11-14T11:00:00+09:00', **self.kwargs)
        self.assertEqual(result['race_id'], 'fixture-race')
        self.assertEqual(len(result['predictions']), 2)

    def test_same_instant_other_timezone_allowed(self):
        result = export_engine_predictions(self.artifact,
            saved_at='2026-11-14T02:00:00Z', **self.kwargs)
        self.assertEqual(len(result['predictions']), 2)

if __name__ == '__main__':
    unittest.main()
