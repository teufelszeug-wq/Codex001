import unittest,sys
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from assemble_official_engine_input import assemble_engine_input
from engine_full_field_bridge import predict_full_field
from prism_engine.contracts import digest
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
    def test_preserves_horse_evidence_provenance(self):
        e=evidence();raw,_=run(e=e)
        self.assertEqual(raw['runners'][0]['provenance'],{
            'source_url':e['1']['source_url'],'available_at':e['1']['available_at'],
            'content_hash':digest(e['1'])})
        self.assertEqual(raw['source']['racecard_sha256'],digest(card))
        self.assertEqual(e['1']['horse_id'],'h1')
    def test_scratches_do_not_compress_barrier_numbers(self):
        c=deepcopy(card);c['active_runners'][1]['horse_no']=3
        e=evidence();e['3']=e.pop('2')
        raw,_=assemble_engine_input(c,e,venue='TEST',surface='TURF',distance_m=1600,
                                    direction='LEFT',class_rating=50,barrier_count=3,
                                    locked_at='2026-11-09T14:00:00+09:00')
        self.assertEqual([r['barrier_no'] for r in raw['runners']],[1,3])
    def test_thursday_entries_use_stable_ids_through_full_field_prediction(self):
        c=deepcopy(card);c['schema']='prism.official_racecard/v2'
        c['declaration_stage']='ENTRIES_CONFIRMED'
        for i,r in enumerate(c['active_runners'],1):
            r.update(horse_id=f'h{i}',horse_no=None,frame_no=None,barrier_no=None)
        e={row['horse_id']:row for row in evidence().values()}
        raw,names=run(c,e)
        result=predict_full_field(raw,'2026-11-09T14:00:00+09:00',names)
        self.assertEqual([r['horse_id'] for r in result['diagnoses']],['h1','h2'])
        self.assertTrue(all(r['horse_no'] is None for r in result['diagnoses']))
        self.assertTrue(all(r['frame_no'] is None for r in result['diagnoses']))
        self.assertAlmostEqual(sum(r['win_probability'] for r in result['diagnoses']),1.)
    def test_official_identity_cannot_be_overridden_by_evidence(self):
        c=deepcopy(card);c['schema']='prism.official_racecard/v2'
        c['declaration_stage']='DRAW_CONFIRMED'
        for i,r in enumerate(c['active_runners'],1):r['horse_id']=f'h{i}'
        e={row['horse_id']:row for row in evidence().values()};e['h1']['horse_id']='other'
        with self.assertRaisesRegex(ValueError,'identity mismatch'):run(c,e)
if __name__=='__main__':unittest.main()
