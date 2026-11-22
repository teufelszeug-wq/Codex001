import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from prism_engine.contracts import digest
from engine_full_field_bridge import predict_full_field

def sample():
    runners=[]
    for i in range(1,4):
        runners.append({'horse_id':f'h{i}','horse_no':i,'frame_no':i,'barrier_no':i,
                        'carried_weight':55,'history':[]})
    raw={'schema':'prism.engine.raw/v1','mode':'SYNTHETIC',
         'race':{'race_id':'SYNTHETIC-ENGINE','venue':'TEST','surface':'TURF',
                 'distance_m':1600,'direction':'LEFT','class_rating':50,
                 'cutoff':'2026-11-09T15:00:00+09:00','barrier_count':3},
         'runners':runners,
         'source':{'source_id':'SYNTHETIC_FIXTURE','available_at':'2026-11-09T13:00:00+09:00','content_hash':''}}
    raw['source']['content_hash']=digest({k:v for k,v in raw.items() if k!='source'})
    return raw

class TestBridge(unittest.TestCase):
    def test_full_field_probabilities(self):
        raw=sample()
        result=predict_full_field(raw,'2026-11-09T14:00:00+09:00',{f'h{i}':f'架空馬{i}' for i in range(1,4)})
        self.assertEqual(len(result['diagnoses']),3)
        self.assertAlmostEqual(sum(d['win_probability'] for d in result['diagnoses']),1,places=6)
        self.assertFalse(result['performance_validated'])
    def test_missing_horse_name_fails(self):
        with self.assertRaisesRegex(ValueError,'all horse IDs'):
            predict_full_field(sample(),'2026-11-09T14:00:00+09:00',{'h1':'架空馬1'})
    def test_future_lock_fails(self):
        with self.assertRaisesRegex(ValueError,'after cutoff'):
            predict_full_field(sample(),'2026-11-09T15:01:00+09:00',{f'h{i}':f'架空馬{i}' for i in range(1,4)})

if __name__=='__main__':
    unittest.main()
