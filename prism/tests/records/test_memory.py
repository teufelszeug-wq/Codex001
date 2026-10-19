"""Synthetic memory tests only; never access the imported private database."""
from pathlib import Path
from copy import deepcopy
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests/dialogue'))
from test_contracts import make_context,records_fixture
from prism_records import RecordStore
from prism_records.discussion import save_discussion
from prism_records.memory import agent_horse_memory,prepare_race_memory,verify_race_memory
from prism_records.store import digest
from prism_records.updates import SourceUpdates
from unittest.mock import patch


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.store=RecordStore(':memory:');self.addCleanup(self.store.close)
        self.context=make_context();self.records=records_fixture(self.context)
        self.store.add_race(self.context['race_id'],{'cutoff':self.context['cutoff']})
        self.horses={}
        for r in self.context['roster']:
            h=self.store.add_horse('synthetic:'+r['horse_id'],'同名')
            self.horses[r['horse_id']]=h
            self.store.add_entry(self.context['race_id'],r['horse_no'],h,frame_no=r['frame_no'])
        self.horse=self.horses['h1']
    def memory(self,**kwargs):
        return agent_horse_memory(self.store,'RIO',self.horse,kwargs.pop('as_of','2026-01-02T12:00:00+09:00'),**kwargs)
    def save(self,selection=False,mode='ROLE_SIMULATION'):
        self.records['execution_mode']=mode
        if selection:
            t=next(t for t in self.records['turns'] if t['agent_id']=='RIO' and t['horse_id']=='h1' and t['stage']=='FINAL')
            self.records['selections']=[{'agent_id':'RIO','horse_id':'h1','selection':'TOP_PICK','turn_id':t['turn_id']}]
        save_discussion(self.store,self.context,self.records,self.horses)
    def test_known_database_is_not_prior_endorsement(self):
        m=self.memory();self.assertEqual(m['prior_entity_entries_count'],1)
        self.assertTrue(m['familiarity']['prohibit_first_meeting_claim'])
        self.assertTrue(m['familiarity']['prohibit_invented_past_endorsement'])
        self.assertEqual(m['past_top_picks_count'],0)
    def test_explicit_role_selection_is_labelled(self):
        self.save(selection=True);m=self.memory()
        self.assertEqual(m['past_top_picks_count'],1)
        self.assertEqual(m['past_top_picks'][0]['history_type'],'ROLE_SIMULATION_ATTRIBUTED_HISTORY')
        self.assertFalse(m['familiarity']['automatic_current_selection_allowed'])
        self.assertFalse(m['independent_execution_verified'])
    def test_no_selection_inferred_from_prose(self):
        for t in self.records['turns']:
            if t['agent_id']=='RIO':t['text']='この馬を本命にしました '+t['turn_id']
        self.save();self.assertEqual(self.memory()['past_top_picks_count'],0)
    def test_template_not_personal_history(self):
        self.save(selection=True,mode='TEMPLATE');m=self.memory()
        self.assertEqual(m['prior_personal_discussions_count'],0)
        self.assertEqual(m['past_top_picks_count'],0)
    def test_current_race_excluded(self):
        self.save(selection=True);m=self.memory(current_race_id=self.context['race_id'])
        self.assertEqual(m['prior_entity_entries_count'],0);self.assertEqual(m['past_top_picks_count'],0)
    def test_future_discussion_excluded(self):
        self.save(selection=True);m=self.memory(as_of='2025-12-31T12:00:00+09:00')
        self.assertEqual(m['prior_personal_discussions_count'],0)
    def test_future_discussion_on_prior_race_excluded(self):
        self.save(selection=True)
        self.store.conn.execute("UPDATE discussions SET occurred_at='2026-01-03T12:00:00+09:00'")
        self.assertEqual(self.memory()['past_top_picks_count'],0)
    def test_declared_timestamp_tamper_cannot_redate_memory(self):
        self.save(selection=True)
        self.store.conn.execute("UPDATE discussions SET occurred_at='2025-12-31T12:00:00+09:00'")
        self.assertEqual(self.memory()['prior_personal_discussions_count'],0)
    def test_names_do_not_join_entities(self):
        self.save(selection=True)
        other=self.store.add_horse('another-source:h1','同名')
        m=agent_horse_memory(self.store,'RIO',other,'2026-01-02T12:00:00+09:00')
        self.assertEqual(m['prior_entity_entries_count'],0);self.assertEqual(m['past_top_picks_count'],0)
    def test_other_agent_not_attributed_to_rio(self):
        self.save(selection=True)
        m=agent_horse_memory(self.store,'OTHER',self.horse,'2026-01-02T12:00:00+09:00')
        self.assertEqual(m['prior_personal_discussions_count'],0)
    def test_unknown_and_post_observations_not_evidence(self):
        self.store.add_observation(self.horse,self.context['race_id'],{'secret_value':'UNKNOWN'},'unknown')
        self.store.add_observation(self.horse,self.context['race_id'],{'phase':'POST','result':123},'post',
            '2026-01-01T11:00:00+09:00','POST_ONLY')
        m=self.memory();self.assertEqual(m['eligible_pre_observation_refs_count'],0)
        self.assertEqual(m['excluded']['post_or_unknown_observations'],2)
        self.assertNotIn('secret_value',str(m));self.assertNotIn('123',str(m['eligible_pre_observation_refs']))
    def test_no_database_mutation(self):
        self.save(selection=True);before=list(self.store.conn.iterdump())
        a=self.memory();b=self.memory()
        self.assertEqual(a,b);self.assertEqual(before,list(self.store.conn.iterdump()))
    def versioned_observations(self):
        updates=SourceUpdates(self.store)
        args={'subject_type':'HORSE','entity_id':self.horse,'race_id':self.context['race_id'],
              'fact_key':'workout','schema_id':'workout/v1','source_ref':'synthetic:workout',
              'temporal_class':'PRE_AVAILABLE','phase':'PRE'}
        first=updates.append(**args,payload={'seconds':52},available_at='2026-01-01T08:00:00+09:00',
                             recorded_at='2026-01-01T09:00:00+09:00')['version']
        second=updates.append(**args,payload={'seconds':51},available_at='2026-01-01T08:30:00+09:00',
                              recorded_at='2026-01-03T09:00:00+09:00',prior_id=first['id'],correction=True)['version']
        return first,second
    def test_later_recorded_correction_hidden_until_recorded(self):
        old,new=self.versioned_observations()
        m=self.memory(as_of='2026-01-02T12:00:00+09:00')
        self.assertEqual([r['observation_id'] for r in m['eligible_pre_observation_refs']],[old['observation_id']])
        self.assertEqual(m['excluded']['invalid_observations'],1)
        self.assertNotIn(new['observation_id'],str(m['eligible_pre_observation_refs']))
    def test_correction_replaces_old_evidence_in_memory(self):
        old,new=self.versioned_observations()
        m=self.memory(as_of='2026-01-04T12:00:00+09:00')
        self.assertEqual([r['observation_id'] for r in m['eligible_pre_observation_refs']],[new['observation_id']])
        self.assertNotIn(old['observation_id'],str(m['eligible_pre_observation_refs']))
    def test_legacy_observation_without_ledger_still_available(self):
        obs=self.store.add_observation(self.horse,self.context['race_id'],{'phase':'PRE','score':1},'legacy',
            '2026-01-01T08:00:00+09:00','PRE_AVAILABLE')
        before=list(self.store.conn.iterdump())
        self.assertEqual(self.memory()['eligible_pre_observation_refs'][0]['observation_id'],obs)
        self.assertEqual(before,list(self.store.conn.iterdump()))
        self.assertFalse(SourceUpdates(self.store)._has_schema())
    def test_roster_prefetch_reads_update_ledger_once_for_all_agents(self):
        self.versioned_observations()
        self.store.add_race('next-memory',{'cutoff':'2026-01-05T12:00:00+09:00'})
        self.store.add_entry('next-memory',1,self.horse)
        original=SourceUpdates.observation_selection
        calls=[]
        def wrapped(instance,*args,**kwargs):
            calls.append(1)
            return original(instance,*args,**kwargs)
        with patch.object(SourceUpdates,'observation_selection',wrapped):
            snapshot=prepare_race_memory(self.store,'next-memory','2026-01-04T12:00:00+09:00',['RIO','OTHER'])
        self.assertEqual(len(calls),1)
        self.assertEqual(len(snapshot['shared_pre_observation_refs']),1)
    def test_update_ledger_tamper_stops_memory(self):
        self.versioned_observations()
        self.store.conn.execute('DROP TRIGGER fact_no_update')
        self.store.conn.execute("UPDATE entity_fact_versions SET review_status='PENDING_CONFLICT'")
        with self.assertRaisesRegex(ValueError,'ledger integrity'): self.memory()
    def test_bad_timezone_rejected(self):
        with self.assertRaises(ValueError):self.memory(as_of='2026-01-02T12:00:00')
    def test_archived_schedule_count_is_not_availability_proof(self):
        self.store.add_race('archive',{'reconstructed_pre':{'values':{'date':'20251201','start':'0900'}}})
        self.store.add_entry('archive',1,self.horse)
        m=self.memory();self.assertEqual(m['prior_entity_entries_count'],2)
        self.assertFalse(m['source_authenticity_verified'])
    def test_invalid_cutoff_is_unknown_not_query_failure(self):
        self.store.add_race('badtime',{'cutoff':'invalid'})
        self.store.add_entry('badtime',1,self.horse)
        self.assertEqual(self.memory()['excluded']['unknown_race_time_entries'],1)
    def test_race_metadata_tamper_excluded(self):
        self.store.conn.execute("UPDATE races SET metadata_json='{}'")
        m=self.memory();self.assertEqual(m['prior_entity_entries_count'],0)
        self.assertEqual(m['excluded']['invalid_record_entries'],1)
    def snapshot(self):
        self.store.add_race('next',{'cutoff':'2026-01-03T12:00:00+09:00'})
        self.store.add_entry('next',1,self.horse,frame_no=1)
        return prepare_race_memory(self.store,'next','2026-01-02T12:00:00+09:00',['RIO'])
    def reseal(self,snap):
        for group in snap['agent_memories'].values():
            for mem in group.values():mem['memory_hash']=digest({k:v for k,v in mem.items() if k!='memory_hash'})
        snap['snapshot_hash']=digest({k:v for k,v in snap.items() if k!='snapshot_hash'})
    def test_race_snapshot_deterministic_and_read_only(self):
        a=self.snapshot();before=list(self.store.conn.iterdump());b=self.snapshot()
        self.assertEqual(a,b);self.assertEqual(before,list(self.store.conn.iterdump()))
        self.assertTrue(verify_race_memory(a,'next',a['as_of']))
    def test_race_snapshot_wrong_target_and_future_rejected(self):
        a=self.snapshot()
        with self.assertRaises(ValueError):verify_race_memory(a,'wrong')
        with self.assertRaises(ValueError):verify_race_memory(a,'next','2026-01-01T12:00:00+09:00')
    def test_race_snapshot_hash_tamper_rejected(self):
        a=self.snapshot();a['as_of']='2026-01-01T12:00:00+09:00'
        with self.assertRaises(ValueError):verify_race_memory(a)
    def test_race_snapshot_resealed_certification_rejected(self):
        a=self.snapshot();a['training_achievement_verified']=True;self.reseal(a)
        with self.assertRaises(ValueError):verify_race_memory(a)
    def test_race_snapshot_nested_unknown_keys_rejected(self):
        a=self.snapshot();a['agent_memories']['RIO'][self.horse]['results']={'winner':'x'};self.reseal(a)
        with self.assertRaises(ValueError):verify_race_memory(a)
    def test_race_snapshot_nested_asof_mismatch_rejected(self):
        a=self.snapshot();a['agent_memories']['RIO'][self.horse]['as_of']='2026-01-01T12:00:00+09:00';self.reseal(a)
        with self.assertRaises(ValueError):verify_race_memory(a)
    def test_race_snapshot_current_selection_rejected_after_reseal(self):
        self.save(selection=True);a=self.snapshot()
        a['agent_memories']['RIO'][self.horse]['past_selections'][0]['race_id']='next';self.reseal(a)
        with self.assertRaises(ValueError):verify_race_memory(a)
    def test_race_snapshot_rider_display_only(self):
        j=self.store.add_jockey('synthetic:rider','騎手',profile={'post_results':{'wins':999}})
        self.store.add_race('rider-race',{})
        self.store.add_entry('rider-race',1,self.horse,jockey_id=j,frame_no=1)
        a=prepare_race_memory(self.store,'rider-race','2026-01-02T12:00:00+09:00',['RIO'])
        self.assertEqual(a['current_riders'][self.horse]['jockey_id'],j)
        self.assertNotIn('post_results',str(a));self.assertTrue(verify_race_memory(a))
        b=self.snapshot();self.assertIsNone(b['current_riders'][self.horse])


if __name__=='__main__':unittest.main()
