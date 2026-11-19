import unittest
from validate_preoff_v2 import validate
BASE={'race_id':'NAR_TEST','off_at':'2026-11-20T20:00:00+09:00','official_racecard_url':'https://example.org/race','full_field_diagnosis_verified':True,'five_topic_roundtable_verified':True,'vertical_newspaper_verified':True,'official_settlement_verified':True}
def f(who,**kw):
 d={'forecaster_id':who,'run_id':'run-'+who,'source_url':'https://example.org/saved','version':'v1','saved_at':'2026-11-19T18:00:00+09:00','execution_mode':'independent','bets_100yen':[{'stake_yen':100}]};d.update(kw);return d
class GateTests(unittest.TestCase):
 def test_valid(self): self.assertTrue(validate(dict(BASE,forecasts=[f('honshi'),f('rio')]))['accepted'])
 def test_after_off(self): self.assertFalse(validate(dict(BASE,forecasts=[f('honshi',saved_at='2026-11-20T20:00:00+09:00'),f('rio')]))['accepted'])
 def test_roleplay(self): self.assertFalse(validate(dict(BASE,forecasts=[f('honshi'),f('rio',execution_mode='single_model_role_text')]))['accepted'])
 def test_stake(self): self.assertFalse(validate(dict(BASE,forecasts=[f('honshi',bets_100yen=[{'stake_yen':150}]),f('rio')]))['accepted'])
 def test_duplicate(self): self.assertFalse(validate(dict(BASE,forecasts=[f('honshi'),f('rio'),f('rio')]))['accepted'])
if __name__=='__main__':unittest.main()
