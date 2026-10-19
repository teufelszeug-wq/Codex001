"""Synthetic imported-history tests; never access the private production snapshot."""
import json
import sqlite3
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from prism_records import RecordStore
from prism_records.legacy_dialogue import stage_legacy_dialogue, legacy_agent_horse_history
from prism_records.memory import agent_horse_memory


class LegacyDialogueTests(unittest.TestCase):
    def setUp(self):
        self.store=RecordStore(':memory:'); self.addCleanup(self.store.close)
        self.horse=self.store.add_horse('fixture:one','同名馬')
        self.other=self.store.add_horse('fixture:two','同名馬')
        self.store.add_race('old-race',{'cutoff':'2026-01-01T12:00:00+09:00'})
        self.store.add_entry('old-race',1,self.horse,frame_no=1)
        self.doc={'race_id':'old-race','recorded_at':None,'execution_mode':'ROLE_SIMULATION',
                  'turns':[{'turn_id':'t1','agent_id':'RIO','horse_id':'legacy-h1',
                            'stage':'FINAL','text':'この馬を応援します。'}],
                  'selections':[{'agent_id':'RIO','horse_id':'legacy-h1','turn_id':'t1','selection':'TOP_PICK'}]}
    def raw(self): return json.dumps(self.doc,ensure_ascii=False).encode()
    def stage(self,**kwargs):
        return stage_legacy_dialogue(self.store,self.raw(),source_ref='fixture:archive',
             imported_at=kwargs.pop('imported_at','2026-10-19T01:00:00Z'),
             horse_map=kwargs.pop('horse_map',{'legacy-h1':self.horse}),**kwargs)
    def history(self,**kwargs):
        return legacy_agent_horse_history(self.store,'RIO',kwargs.pop('horse_id',self.horse),
                 as_of=kwargs.pop('as_of','2026-10-19T02:00:00Z'),**kwargs)
    def test_unknown_time_preserved_without_pre_assessments(self):
        receipt=self.stage(); self.assertEqual(receipt['phase'],'UNKNOWN')
        self.assertEqual(receipt['explicit_top_pick_count'],1)
        self.assertEqual(self.store.conn.execute('SELECT count(*) FROM assessments').fetchone()[0],0)
        old=agent_horse_memory(self.store,'RIO',self.horse,'2026-10-19T02:00:00Z')
        self.assertEqual(old['past_top_picks_count'],0)
        archive=self.history();self.assertEqual(archive['records'][0]['phase'],'UNKNOWN')
        self.assertFalse(archive['pre_evidence_allowed'])
    def test_declared_pre_time_still_not_certified_pre(self):
        self.doc['recorded_at']='2026-01-01T11:00:00+09:00'
        self.assertEqual(self.stage()['phase'],'UNKNOWN')
    def test_declared_post_time_tagged(self):
        self.doc['recorded_at']='2026-01-01T13:00:00+09:00'
        self.assertEqual(self.stage()['phase'],'POST')
        self.assertFalse(self.history()['historical_pre_availability_verified'])
    def test_import_receipt_prevents_historical_visibility(self):
        self.stage(); self.assertEqual(self.history(as_of='2026-02-01T01:00:00Z')['records'],[])
    def test_future_meeting_rejected(self):
        self.doc['recorded_at']='2026-10-20T01:00:00Z'
        with self.assertRaises(ValueError): self.stage()
    def test_only_explicit_selection_counts(self):
        self.doc['turns'][0]['text']='私の本命はこの馬です。'
        self.doc['selections']=[]
        self.assertEqual(self.stage()['explicit_top_pick_count'],0)
        self.assertEqual(self.history()['records'][0]['explicit_selections'],[])
    def test_template_not_personal_history(self):
        self.doc['execution_mode']='TEMPLATE'; self.stage()
        self.assertEqual(self.history()['records'],[])
    def test_unstated_mode_not_personal_history(self):
        del self.doc['execution_mode']; self.stage()
        self.assertEqual(self.history()['records'],[])
    def test_independence_label_not_verification(self):
        self.doc['execution_mode']='INDEPENDENT_EXECUTION'; self.stage()
        self.assertFalse(self.history()['records'][0]['independent_execution_verified'])
    def test_same_name_not_identity_match(self):
        with self.assertRaises(ValueError): self.stage(horse_map={'legacy-h1':self.other})
    def test_source_bytes_not_derived_document(self):
        with self.assertRaises(ValueError):
            stage_legacy_dialogue(self.store,b'{"race_id":"old-race","race_id":"other"}',
                 source_ref='x',imported_at='2026-10-19T01:00:00Z',horse_map={})
    def test_selection_needs_final_matching_agent(self):
        self.doc['selections'][0]['agent_id']='OTHER'
        with self.assertRaises(ValueError): self.stage()
        self.doc['selections'][0]['agent_id']='RIO';self.doc['turns'][0]['stage']='QUESTION'
        with self.assertRaises(ValueError): self.stage()
    def test_idempotent_import_retains_first_receipt(self):
        first=self.stage(); second=self.stage(imported_at='2026-10-19T02:00:00Z')
        self.assertEqual(first['record_id'],second['record_id']); self.assertFalse(second['inserted'])
        self.assertEqual(self.history()['records'][0]['imported_at'],'2026-10-19T01:00:00Z')
    def test_changed_source_appends_without_overwrite(self):
        self.stage();self.doc['turns'][0]['text']='更新した意見';self.stage()
        self.assertEqual(len(self.history()['records']),2)
    def test_corrupted_archive_rejected(self):
        self.stage()
        # Simulate corruption outside the guarded API after explicitly removing its guard.
        self.store.conn.execute('DROP TRIGGER legacy_dialogue_no_update')
        self.store.conn.execute("UPDATE legacy_dialogue_imports SET payload_json='{}'")
        with self.assertRaises(ValueError): self.history()
    def test_sql_update_and_delete_rejected(self):
        self.stage()
        for statement in ("UPDATE legacy_dialogue_imports SET payload_json='{}'",
                          'DELETE FROM legacy_dialogue_imports'):
            with self.assertRaises(sqlite3.IntegrityError): self.store.conn.execute(statement)
        self.assertEqual(len(self.history()['records']),1)
    def test_sql_replace_cannot_bypass_delete_trigger(self):
        self.stage()
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.conn.execute('INSERT OR REPLACE INTO legacy_dialogue_imports SELECT * FROM legacy_dialogue_imports')
        self.assertEqual(len(self.history()['records']),1)
    def test_other_agent_and_current_race_excluded(self):
        self.stage();self.assertEqual(self.history(current_race_id='old-race')['records'],[])
        out=legacy_agent_horse_history(self.store,'OTHER',self.horse,as_of='2026-10-19T02:00:00Z')
        self.assertEqual(out['records'],[])
    def test_read_query_has_no_mutation(self):
        self.stage();before=list(self.store.conn.iterdump());self.history();self.history()
        self.assertEqual(before,list(self.store.conn.iterdump()))
    def test_stage_rolls_back_inside_outer_transaction(self):
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                self.stage(); raise RuntimeError('abort')
        self.assertIsNone(self.store.conn.execute("SELECT 1 FROM sqlite_master WHERE name='legacy_dialogue_imports'").fetchone())


if __name__=='__main__': unittest.main()
