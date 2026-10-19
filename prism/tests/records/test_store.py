from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from prism_records import RecordStore


class RecordTests(unittest.TestCase):
    def setUp(self): self.store=RecordStore(':memory:')
    def tearDown(self): self.store.close()
    def fixture(self):
        s=self.store;h=s.add_horse('source:horse:1','同名');j=s.add_jockey('source:jockey:1','騎手')
        s.add_race('r',{'cutoff':'2026-01-01T12:00:00+09:00'})
        e=s.add_entry('r',1,h,j,1,{'post_result':{'rank':2}})
        return h,j,e
    def test_same_name_different_sources_not_merged(self):
        a=self.store.add_horse('source:a','同名');b=self.store.add_horse('source:b','同名')
        self.assertNotEqual(a,b);self.assertEqual(self.store.summary()['counts']['provisional_horses'],2)
    def test_explicit_canonical_identity_alias(self):
        a=self.store.add_horse('s1','馬',canonical_id='official1')
        b=self.store.add_horse('s2','馬',canonical_id='official1')
        self.assertEqual(a,b);self.assertEqual(self.store.summary()['counts']['horses'],1)
    def test_immutable_entity(self):
        a=self.store.add_horse('source:a','馬')
        self.assertEqual(a,self.store.add_horse('source:a','馬'))
        with self.assertRaises(ValueError):self.store.add_horse('source:a','変更')
    def test_source_identity_cannot_be_remapped(self):
        self.store.add_horse('s1','馬')
        with self.assertRaises(ValueError):self.store.add_horse('s1','馬',canonical_id='official1')
    def test_outer_transaction_rolls_back_nested_calls(self):
        with self.assertRaises(ValueError):
            with self.store.transaction():
                self.store.add_horse('a','馬');self.store.add_race('r',{})
                self.store.add_race('r',{'different':1})
        self.assertEqual(self.store.summary()['counts']['horses'],0)
        self.assertEqual(self.store.summary()['counts']['races'],0)
    def test_unknown_foreign_key(self):
        with self.assertRaises(ValueError):self.store.add_entry('r',1,'unknown')
    def test_entry_collision_and_idempotency(self):
        h,j,e=self.fixture()
        self.assertEqual(e,self.store.add_entry('r',1,h,j,1,{'post_result':{'rank':2}}))
        with self.assertRaises(ValueError):self.store.add_entry('r',1,h,j,2,{})
    def test_observation_idempotent_and_immutable(self):
        h,j,e=self.fixture();s=self.store
        a=s.add_observation(h,'r',{'score':1},'source:obs')
        self.assertEqual(a,s.add_observation(h,'r',{'score':1},'source:obs'))
        with self.assertRaises(ValueError):s.add_observation(h,'r',{'score':2},'source:obs')
        self.assertEqual(s.jockey_profile(j)['observations'][0]['phase'],'UNKNOWN')
    def test_missing_entry_observation_rejected(self):
        h=self.store.add_horse('s','馬');self.store.add_race('r',{})
        with self.assertRaises(ValueError):self.store.add_observation(h,'r',{},'source:obs')
    def test_pre_requires_timestamp(self):
        h,_,_=self.fixture()
        with self.assertRaises(ValueError):self.store.add_observation(h,'r',{'phase':'PRE'},'o')
    def test_pre_rejects_results_and_future_timestamp(self):
        h,_,_=self.fixture()
        for payload,at in [({'phase':'PRE','results':{}},'2026-01-01T11:00:00+09:00'),
                           ({'phase':'PRE'},'2026-01-01T13:00:00+09:00')]:
            with self.assertRaises(ValueError):self.store.add_observation(h,'r',payload,'o',at,'PRE_AVAILABLE')
    def test_pre_rejects_expanded_result_keys(self):
        h,_,_=self.fixture()
        for key in ('winners','winner','settlement','refund_yen','payout_yen','win_payouts','target_result','refund_keys'):
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.store.add_observation(h,'r',{'phase':'PRE','nested':{key:0}},'o',
                                           '2026-01-01T11:00:00+09:00','PRE_AVAILABLE')
    def test_payload_argument_identity_and_time_mismatch(self):
        h,_,_=self.fixture()
        for extra in ({'race_id':'OTHER'},{'horse_id':'OTHER'},{'horse_no':2},
                      {'horse_identity':{'horse_no':2}},{'horse_identity':{'horse_id':'OTHER'}},
                      {'available_at':None},{'temporal_class':'UNKNOWN_TIMESTAMP'}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                self.store.add_observation(h,'r',{'phase':'PRE',**extra},'o',
                                           '2026-01-01T11:00:00+09:00','PRE_AVAILABLE')
    def test_nested_source_cannot_be_promoted_to_pre(self):
        h,_,_=self.fixture()
        for source in ({'temporal_class':'UNKNOWN_TIMESTAMP'},{'available_at':None},
                       {'available_at':'2026-01-01T13:00:00+09:00'},{'mode':'HISTORICAL_RECONSTRUCTION'}):
            with self.subTest(source=source),self.assertRaises(ValueError):
                self.store.add_observation(h,'r',{'phase':'PRE','source':source},'o',
                                           '2026-01-01T11:00:00+09:00','PRE_AVAILABLE')
    def test_valid_pre_and_post_are_separate(self):
        h,_,_=self.fixture()
        self.store.add_observation(h,'r',{'phase':'PRE','mode':'SYNTHETIC'},'pre','2026-01-01T11:00:00+09:00','PRE_AVAILABLE')
        self.store.add_observation(h,'r',{'phase':'POST','result':1},'post','2026-01-01T13:00:00+09:00','POST_ONLY')
        self.assertEqual({x['phase'] for x in self.store.horse_profile(h)['observations']},{'PRE','POST'})
    def test_invalid_temporal_classes(self):
        h,_,_=self.fixture()
        for cls in ('INVENTED','LATE_PRE','POST_ONLY'):
            with self.assertRaises(ValueError):self.store.add_observation(h,'r',{},'o',temporal_class=cls)
    def test_read_only_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'records.sqlite';s=RecordStore(path);h=s.add_horse('s','馬');s.close()
            s=RecordStore(path,read_only=True)
            try:
                self.assertEqual(s.horse_profile(h)['entity']['display_name'],'馬')
                with self.assertRaises(sqlite3.OperationalError):s.add_horse('s2','馬2')
            finally:s.close()
    def test_database_integrity(self):
        self.fixture()
        self.assertEqual(self.store.conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(self.store.conn.execute('PRAGMA foreign_key_check').fetchall(),[])
    def assessment(self,subject='HORSE',horse=None):
        h,j,e=self.fixture()
        self.store.conn.execute("INSERT OR IGNORE INTO discussions(id,race_id,phase,mode,payload_json,content_hash) VALUES('d','r','PRE','SYNTHETIC','{}','test')")
        self.store.conn.execute('INSERT INTO assessments(id,discussion_id,entry_id,horse_id,jockey_id,subject_type,phase,mode,agent_id,turn_id,claim_type,payload_json,content_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (subject,'d',e,horse or h,j,subject,'PRE','SYNTHETIC','agent',subject,'RESEARCH','{}','test'))
        return h,j
    def test_horse_opinion_is_not_jockey_opinion(self):
        h,j=self.assessment('HORSE');self.assessment('JOCKEY')
        profile=self.store.jockey_profile(j)
        self.assertEqual(len(profile['assessments']),1)
        self.assertEqual(profile['assessments'][0]['subject_type'],'JOCKEY')
        self.assertEqual(len(profile['related_horse_assessments']),1)
        self.assertEqual(len(self.store.horse_profile(h)['assessments']),1)
    def test_assessment_entry_mismatch_rejected(self):
        h2=self.store.add_horse('another','別馬')
        with self.assertRaises(sqlite3.IntegrityError):self.assessment(horse=h2)


if __name__=='__main__':unittest.main()
