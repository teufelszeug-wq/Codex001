from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from prism_engine import predict
from prism_engine.contracts import digest
from prism_engine.recovered_observations import extract_nar_candidate,extract_jra_candidate


class QuarantineAdapterTests(unittest.TestCase):
    def nar(self):
        return {'馬番':'1','枠番':'2','負担重量':'☆54.0','馬体重':'472','馬体重増減':'+12',
                '騎手名':'SYNTHETIC_RIDER','騎手成績':'1-2-3-4','着順':'1','上がり3F':'36.2','人気':'1','払戻':'1000'}

    def test_allowlisted_raw_values_are_extracted_without_outcomes(self):
        result=extract_nar_candidate(self.nar(),'SYNTHETIC_RACE','SYNTHETIC_SOURCE')
        observations=result['observations']
        self.assertEqual(observations['carried_weight_kg'],54)
        self.assertEqual(observations['body_weight_kg'],472)
        self.assertEqual(observations['body_weight_change_kg'],12)
        self.assertEqual(observations['jockey_counts_unverified']['rides'],10)
        for field in ('着順','上がり3F','人気','払戻'):self.assertNotIn(field,str(result))

    def test_unknown_timestamp_and_identity_remain_unresolved(self):
        result=extract_nar_candidate(self.nar(),'SYNTHETIC_RACE','SYNTHETIC_SOURCE')
        self.assertIsNone(result['source']['available_at'])
        self.assertIsNone(result['horse_identity']['horse_id'])
        self.assertFalse(result['engine_ready']);self.assertFalse(result['pre_available_certified'])
        self.assertEqual(result['source']['temporal_class'],'UNKNOWN_TIMESTAMP')

    def test_pre_available_promotion_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'quarantine'):
            extract_nar_candidate(self.nar(),'SYNTHETIC_RACE','SYNTHETIC_SOURCE',mode='PRE_AVAILABLE')

    def test_quarantine_schema_cannot_be_engine_raw(self):
        result=extract_nar_candidate(self.nar(),'SYNTHETIC_RACE','SYNTHETIC_SOURCE')
        with self.assertRaises(ValueError):predict(result,'2026-01-01T09:55:00+09:00')

    def test_changes_to_outcomes_do_not_change_observations(self):
        first=self.nar();second=deepcopy(first);second['着順']='9';second['上がり3F']='99.9'
        a=extract_nar_candidate(first,'SYNTHETIC_RACE','SYNTHETIC_SOURCE')
        b=extract_nar_candidate(second,'SYNTHETIC_RACE','SYNTHETIC_SOURCE')
        self.assertEqual(a['observations'],b['observations'])
        self.assertNotEqual(a['source']['source_record_hash'],b['source']['source_record_hash'])

    def test_jra_frame_image_and_weight_markers_are_supported(self):
        raw={'num':'3','waku':'','weight':'▲53.0','h_weight':'480(-8)','jockey':'SYNTHETIC_RIDER','place':'1','f_time':'35.9'}
        result=extract_jra_candidate(raw,'SYNTHETIC_RACE','SYNTHETIC_SOURCE',frame_image_alt='枠2黒')
        self.assertEqual(result['observations']['frame_no'],2)
        self.assertEqual(result['observations']['carried_weight_kg'],53)
        self.assertEqual(result['observations']['body_weight_change_kg'],-8)
        self.assertNotIn('place',result['observations']);self.assertNotIn('f_time',result['observations'])

    def test_missing_body_weight_never_becomes_zero_or_carried_weight(self):
        raw=self.nar();raw['馬体重']='---';raw['馬体重増減']='---'
        observations=extract_nar_candidate(raw,'SYNTHETIC_RACE','SYNTHETIC_SOURCE')['observations']
        self.assertIsNone(observations['body_weight_kg']);self.assertIsNone(observations['body_weight_change_kg'])
        self.assertEqual(observations['carried_weight_kg'],54)

    def test_candidate_integrity_is_reproducible(self):
        a=extract_nar_candidate(self.nar(),'SYNTHETIC_RACE','SYNTHETIC_SOURCE')
        b=extract_nar_candidate(self.nar(),'SYNTHETIC_RACE','SYNTHETIC_SOURCE')
        self.assertEqual(a,b)
        self.assertEqual(a['candidate_hash'],digest({k:v for k,v in a.items() if k!='candidate_hash'}))


if __name__=='__main__':unittest.main()
