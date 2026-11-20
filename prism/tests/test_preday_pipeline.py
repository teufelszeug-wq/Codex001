import json
import tempfile
import unittest
from pathlib import Path
from preday_pipeline import save_preday_record

BASE = dict(race_id='20261121_JRA_01_11', horse_id='H001', horse_name='テスト馬', forecaster_id='PRISM_MAIN', source_id='official:verified:example', saved_at='2026-11-20T10:00:00+09:00', version='preday-v1', scheduled_start_at='2026-11-21T15:30:00+09:00', source_authenticity_verified=True, record_type='preday_forecast')
class TestPipeline(unittest.TestCase):
    def test_write_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'forecast.json'
            save_preday_record(BASE,p,as_of='2026-11-20T12:00:00+09:00')
            self.assertEqual(json.loads(p.read_text())['horse_name'],'テスト馬')
            with self.assertRaises(FileExistsError): save_preday_record(BASE,p,as_of='2026-11-20T12:00:00+09:00')
    def test_reject_unverified_without_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'forecast.json'
            with self.assertRaises(ValueError): save_preday_record({**BASE,'source_authenticity_verified':False},p,as_of='2026-11-20T12:00:00+09:00')
            self.assertFalse(p.exists())
    def test_reject_race_day(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): save_preday_record({**BASE,'saved_at':'2026-11-21T09:00:00+09:00'},Path(d)/'x.json',as_of='2026-11-21T10:00:00+09:00')
if __name__=='__main__': unittest.main()
