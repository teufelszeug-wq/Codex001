"""Regression tests for the fail-closed experimental engine export boundary."""
import unittest
from datetime import datetime, timedelta, timezone
from engine_prediction_export import export_engine_predictions

class EngineProbabilityTests(unittest.TestCase):
    def setUp(self):
        now = datetime.now(timezone.utc)
        self.saved = now.isoformat()
        self.artifact = {
            'schema': 'prism.engine.prediction/v1', 'mode': 'PRE_AVAILABLE',
            'source_authenticity_verified': True, 'race_id': '20261116-JRA-TEST-01',
            'locked_at': (now-timedelta(hours=2)).isoformat(),
            'cutoff': (now-timedelta(hours=1)).isoformat(),
            'win': {'h1': 0.6, 'h2': 0.4},
        }
        self.kwargs = dict(horses={'h1':'架空馬甲','h2':'架空馬乙'}, predictor_id='TEST',
                           source='verified-fixture', saved_at=self.saved, version='v1',
                           scheduled_start_at=(now+timedelta(hours=2)).isoformat())

    def test_valid_distribution(self):
        result = export_engine_predictions(self.artifact, **self.kwargs)
        self.assertEqual(len(result['predictions']), 2)

    def test_negative_probability_rejected(self):
        self.artifact['win'] = {'h1': -0.1, 'h2': 1.1}
        with self.assertRaisesRegex(ValueError, 'invalid_win_probability'):
            export_engine_predictions(self.artifact, **self.kwargs)

    def test_nan_rejected(self):
        self.artifact['win'] = {'h1': float('nan'), 'h2': 0.4}
        with self.assertRaisesRegex(ValueError, 'invalid_win_probability'):
            export_engine_predictions(self.artifact, **self.kwargs)

    def test_boolean_rejected(self):
        self.artifact['win'] = {'h1': True, 'h2': 0}
        with self.assertRaisesRegex(ValueError, 'invalid_win_probability'):
            export_engine_predictions(self.artifact, **self.kwargs)

    def test_unnormalized_distribution_rejected(self):
        self.artifact['win'] = {'h1': 0.5, 'h2': 0.4}
        with self.assertRaisesRegex(ValueError, 'unnormalized_win_probabilities'):
            export_engine_predictions(self.artifact, **self.kwargs)

if __name__ == '__main__':
    unittest.main()
