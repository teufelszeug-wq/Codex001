"""Regression cases for forecast publication preflight."""
import importlib.util
import unittest
from pathlib import Path
script=Path(__file__).resolve().parents[1]/'scripts'/'forecast_preflight.py'
spec=importlib.util.spec_from_file_location('forecast_preflight',script)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
validate=module.validate
BASE={'race_id':'fixture-race','version':1,'saved_at':'2026-11-15T20:00:00+09:00','off_at':'2026-11-16T15:00:00+09:00','source_refs':['official:fixture'],'records':[{'forecaster_id':'rio','decision':'bet','bets':[{'horse_name':'テスト馬','stake_yen':100}]}]}
class TestPreflight(unittest.TestCase):
    def test_valid(self): self.assertEqual(validate(BASE),[])
    def test_abstain(self): self.assertEqual(validate({**BASE,'records':[{'forecaster_id':'rio','decision':'abstain'}]}),[])
    def test_missing_horse(self): self.assertIn('record[0]:bet[0]:horse_name',validate({**BASE,'records':[{'forecaster_id':'rio','decision':'bet','bets':[{'stake_yen':100}]}]}))
    def test_invalid_stake(self): self.assertIn('record[0]:bet[0]:stake_yen',validate({**BASE,'records':[{'forecaster_id':'rio','decision':'bet','bets':[{'horse_name':'テスト馬','stake_yen':150}]}]}))
    def test_post_off(self): self.assertIn('invalid:pre_off_time',validate({**BASE,'saved_at':'2026-11-16T16:00:00+09:00'}))
    def test_duplicate(self): self.assertIn('record[1]:duplicate_forecaster_id',validate({**BASE,'records':[BASE['records'][0],BASE['records'][0]]}))
    def test_bool_stake(self): self.assertIn('record[0]:bet[0]:stake_yen',validate({**BASE,'records':[{'forecaster_id':'rio','decision':'bet','bets':[{'horse_name':'テスト馬','stake_yen':True}]}]}))
if __name__=='__main__': unittest.main()
