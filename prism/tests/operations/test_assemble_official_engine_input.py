import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from assemble_official_engine_input import assemble_engine_input
card={'schema':'prism.official_racecard/v1','source_verified':True,'race_id':'SYNTHETIC-JRA-1',
      'race_name':'架空競走','off_at':'2026-11-09T15:00:00+09:00',
      'captured_at':'2026-11-09T13:00:00+09:00','official_url':'https://www.jra.go.jp/JRADB/',
      'active_runners':[{'horse_no':1,'horse_name':'架空馬A','frame_no':1},
                        {'horse_no':2,'horse_name':'架空馬B','frame_no':1}]}
def history():
    return [{'occurred_at':'2026-10-01T10:00:00+09:00',
             'available_at':'2026-10-01T12:00:00+09:00',
             'performance_score':60,'distance_m':1600,'surface':'TURF',
             'direction':'LEFT','class_rating':50,'venue':'TEST'}]
def evidence():
    return {str(i):{'horse_id':f'h{i}','source_url':'https://www.jra.go.jp/JRADB/',
                    'available_at':'2026-11-08T10:00:00+09:00','carried_weight':55,
                    'history':history()} for i in (1,2)}
def run(c=card,e=None):
    return assemble_engine_input(c,e if e is not None else evidence(),venue='TEST',surface='TURF',
                                 distance_m=1600,direction='LEFT',class_rating=50,
                                 barrier_count=2,locked_at='2026-11-09T14:00:00+09:00')
class TestJoin(unittest.TestCase):
    def test_full_field_and_provenance(self):
        raw,names=run()
        self.assertEqual(raw['mode'],'PRE_AVAILABLE')
        self.assertEqual(names,{'h1':'架空馬A','h2':'架空馬B'})
    def test_refuse_unverified_card(self):
        with self.assertRaisesRegex(ValueError,'not been verified'):run({**card,'source_verified':False})
    def test_refuse_missing_horse(self):
        e=evidence();del e['2']
        with self.assertRaisesRegex(ValueError,'complete evidence'):run(e=e)
    def test_refuse_future_evidence(self):
        e=evidence();e['1']['available_at']='2026-11-09T14:30:00+09:00'
        with self.assertRaisesRegex(ValueError,'future'):run(e=e)
    def test_refuse_no_history(self):
        e=evidence();e['1']['history']=[]
        with self.assertRaisesRegex(ValueError,'prior history'):run(e=e)
if __name__=='__main__':unittest.main()
