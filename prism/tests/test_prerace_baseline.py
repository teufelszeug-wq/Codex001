import unittest
from prerace_baseline import forecast_field

R = {'source_authenticity_verified': True, 'scheduled_start_at':'2026-11-22T15:00:00+09:00', 'horses':[{'horse_id':'h1'}, {'horse_id':'h2'}]}
F = [{'horse_id':'h1','observed_at':'2026-11-21T12:00:00+09:00','pre_race_score':1.0},{'horse_id':'h2','observed_at':'2026-11-21T12:00:00+09:00','pre_race_score':0.0}]
C='2026-11-21T18:00:00+09:00'
class BaselineTests(unittest.TestCase):
 def test_complete_probabilities(self):
  out=forecast_field(R,F,cutoff_at=C)
  self.assertEqual(len(out),2)
  self.assertAlmostEqual(sum(x['prediction']['win_probability'] for x in out),1)
 def test_leakage_rejected(self):
  bad=[dict(x) for x in F];bad[0]['observed_at']='2026-11-22T10:00:00+09:00'
  with self.assertRaises(ValueError):forecast_field(R,bad,cutoff_at=C)
 def test_missing_runner_rejected(self):
  with self.assertRaises(ValueError):forecast_field(R,F[:1],cutoff_at=C)
 def test_after_start_rejected(self):
  with self.assertRaises(ValueError):forecast_field(R,F,cutoff_at='2026-11-22T15:00:00+09:00')
 def test_nan_rejected(self):
  bad=[dict(x) for x in F];bad[0]['pre_race_score']=float('nan')
  with self.assertRaises(ValueError):forecast_field(R,bad,cutoff_at=C)
if __name__=='__main__':unittest.main()
