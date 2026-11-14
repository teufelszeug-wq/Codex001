import unittest
from engine_prediction_export import export_engine_predictions

A = {'schema':'prism.engine.prediction/v1','mode':'PRE_AVAILABLE',
     'source_authenticity_verified':True,'race_id':'TEST-1',
     'locked_at':'2026-11-14T10:00:00+09:00',
     'cutoff':'2026-11-15T15:00:00+09:00',
     'win':{'h1':.6,'h2':.4}}
K = {'horses':{'h1':'馬A','h2':'馬B'},'predictor_id':'engine',
     'source':'official','saved_at':'2026-11-14T10:01:00+09:00',
     'version':'pre-v1','scheduled_start_at':'2026-11-15T15:00:00+09:00'}

class ExportTests(unittest.TestCase):
    def test_success(self):
        self.assertEqual(len(export_engine_predictions(A, **K)['predictions']), 2)
    def test_unverified(self):
        with self.assertRaisesRegex(ValueError, 'unverified'):
            export_engine_predictions({**A,'source_authenticity_verified':False}, **K)
    def test_horse_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'horse_id_mismatch'):
            export_engine_predictions(A, **{**K,'horses':{'h1':'馬A'}})
    def test_future_save(self):
        with self.assertRaisesRegex(ValueError, 'timeline'):
            export_engine_predictions(A, **{**K,'saved_at':'2026-11-15T15:01:00+09:00'})
    def test_historical(self):
        with self.assertRaisesRegex(ValueError, 'non_live'):
            export_engine_predictions({**A,'mode':'HISTORICAL_RECONSTRUCTION'}, **K)

if __name__ == '__main__':
    unittest.main()
