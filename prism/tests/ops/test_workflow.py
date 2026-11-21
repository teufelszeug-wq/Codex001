"""Persistent integration checks with explicitly SYNTHETIC API responses only."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0]=[str(Path(__file__).resolve().parents[2]/'src')]
from prism_engine.contracts import digest
from prism_ops.characters import build_character_snapshot
from prism_ops.provider import OpenAIProvider, ProviderBlocked
from prism_ops.reader import archive
from prism_ops.runtime import execute_job
from prism_ops.store import Store
from prism_ops.workflow import TOPICS, operation_race, publish_saved, run_pre_day


class WorkflowClock:
    def __init__(self):
        self.at=datetime(2026,11,12,9,tzinfo=timezone.utc)

    def __call__(self):
        self.at+=timedelta(seconds=1)
        return self.at.isoformat()


def workflow_inputs():
    records=[{'agent_id':identifier,'name':name,'role':role,
              'configuration':{'instruction':'SYNTHETIC test persona; no actual canonical settings claimed'},
              'source_page_url':'https://www.notion.so/'+str(index)*32}
             for index,(identifier,name,role) in enumerate([
                 ('00000000-0000-0000-0000-000000000001','篠宮 律','editor'),
                 ('00000000-0000-0000-0000-000000000002','りお','reporter'),
                 ('00000000-0000-0000-0000-000000000003','架空専門担当','specialist')],1)]
    snapshot=build_character_snapshot(records,source_url='https://www.notion.so/'+'a'*32,
                                       captured_at='2026-11-12T08:00:00+00:00')
    runners=[{'horse_id':'synthetic-h'+str(i),'horse_no':i,'frame_no':i,'barrier_no':i,
              'horse_name':'架空馬'+str(i),'status':'DECLARED'} for i in (1,2)]
    card={'schema':'prism.official_racecard/v2','race_id':'SYNTHETIC-WORKFLOW',
          'authority':'JRA','race_name':'架空結合競走','source_verified':True,
          'off_at':'2026-11-13T15:00:00+09:00','captured_at':'2026-11-12T08:00:00+00:00',
          'declaration_stage':'DRAW_CONFIRMED','active_runners':runners,
          'official_url':'https://www.jra.go.jp/JRADB/SYNTHETIC-TEST-ONLY'}
    raw={'schema':'prism.engine.raw/v2','mode':'SYNTHETIC',
         'race':{'race_id':card['race_id'],'venue':'TEST','surface':'TURF','distance_m':1600,
                 'direction':'LEFT','class_rating':50,'cutoff':card['off_at'],
                 'barrier_count':2,'declaration_stage':'DRAW_CONFIRMED'},
         'runners':[{k:v for k,v in r.items() if k in {'horse_id','horse_no','frame_no','barrier_no'}}|
                    {'carried_weight':55,'history':[]} for r in runners],
         'source':{'source_id':'SYNTHETIC-ONLY','available_at':card['captured_at'],'content_hash':''}}
    raw['source']['content_hash']=digest({k:v for k,v in raw.items() if k!='source'})
    return card,snapshot,raw


class SyntheticWorkflowTransport:
    def __init__(self, *, fail_on=None):
        self.calls=[]
        self.fail_on=fail_on

    def __call__(self,body,timeout):
        request=json.loads(body['input'])
        self.calls.append(request)
        if self.fail_on is not None and len(self.calls)==self.fail_on:
            raise TimeoutError('SYNTHETIC interrupted provider call')
        context=request['race_evidence'];stage=request['stage']
        character=request['canonical_character'];identifier=character['agent_id']
        if stage=='RESPONSE':
            previous=context['prior_turns']
            output={'text':'SYNTHETIC '+context['topic']['topic_id']+' '+identifier,
                    'evidence_refs':[context['source_refs'][0]],'stance':'CHALLENGE',
                    'responds_to':previous[-1]['execution_id'] if previous else None}
        else:
            output={'diagnoses':[{'horse_id':r['horse_id'],'reason':'SYNTHETIC full diagnosis'}
                                 for r in context['runners']],
                    'picks':[{'horse_id':context['runners'][0]['horse_id'],'mark':'◎','reason':'SYNTHETIC reason'}],
                    'tickets':[{'type':'WIN','horse_nos':[1],'stake_yen':200}],
                    'skip_reason':'','change_reason':'SYNTHETIC retained after discussion' if stage=='FINAL' else ''}
        return {'id':'resp_synthetic_'+digest(body),'status':'completed','output':[
            {'type':'message','content':[{'type':'output_text','text':json.dumps(output,ensure_ascii=False)}]}]}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.clock=WorkflowClock()
        self.store=Store(Path(self.temp.name)/'private',now=self.clock)
        self.card,self.snapshot,self.raw=workflow_inputs()
        self.race=operation_race(self.card,self.snapshot)
        self.transport=SyntheticWorkflowTransport()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def provider(self,transport=None):
        return OpenAIProvider(model='SYNTHETIC-injected-test-only',transport=transport or self.transport,
                              now=self.clock)

    def run_workflow(self,provider=None):
        return run_pre_day(self.race,self.snapshot,self.raw,self.store,provider or self.provider(),
                           now=self.clock,render=False)

    def test_initial_five_topics_final_order_and_uuid_roster(self):
        result=self.run_workflow()
        stages=[x['stage'] for x in self.transport.calls]
        self.assertEqual(stages,['PRELIMINARY']*3+['RESPONSE']*15+['FINAL']*3)
        self.assertEqual([t['topic_id'] for t in result['bundle']['discussions']],[t[0] for t in TOPICS])
        self.assertEqual(set(result['bundle']['final']),set(self.race['required_forecasters']))
        self.assertEqual(result['bundle']['characters'],self.snapshot['records'])
        self.assertEqual(result['bundle']['mode'],'SYNTHETIC')
        for request in self.transport.calls[3:18]:
            context=request['race_evidence']
            self.assertEqual(set(context['preliminary']),set(self.race['required_forecasters']))
        for request in self.transport.calls[-3:]:
            self.assertEqual(len(request['race_evidence']['discussions']),5)
        status=json.loads(self.store.jobs()[0]['detail'])
        self.assertEqual(status['independent_executions'],0)
        self.assertEqual(status['official_publications'],0)
        self.assertTrue(all(r['receipt']['execution_mode']=='SYNTHETIC'
                            for r in result['execution_receipts'].values()))

    def test_cached_replay_makes_no_more_api_calls(self):
        first=self.run_workflow()
        second=self.run_workflow()
        self.assertEqual(len(self.transport.calls),21)
        self.assertEqual(first,second)

    def test_editorial_byline_is_bound_only_to_predictions_without_new_persona(self):
        snapshot_before=deepcopy(self.snapshot)
        result=self.run_workflow()
        editor=next(r for r in self.snapshot['records'] if r['role']=='editor')
        expected={'byline':'本紙','role':'EDITORIAL'}
        for request in self.transport.calls:
            character=request['canonical_character']
            context=request['race_evidence']
            if character['agent_id']==editor['agent_id'] and request['stage'] in {'PRELIMINARY','FINAL'}:
                self.assertEqual(context['output_attribution'],expected)
            else:
                self.assertNotIn('output_attribution',context)
            if character['agent_id']==editor['agent_id']:
                self.assertEqual(character['name'],'篠宮 律')
                self.assertEqual(character['configuration'],editor['configuration'])
                self.assertEqual(character['source_page_url'],editor['source_page_url'])
        self.assertEqual(self.snapshot,snapshot_before)
        self.assertEqual(len(result['bundle']['characters']),3)
        for stage,group in [('PRELIMINARY','preliminary'),('FINAL','final')]:
            output=result['bundle'][group][editor['agent_id']]
            self.assertEqual(output['forecaster_id'],editor['agent_id'])
            execution=result['execution_receipts'][output['execution_id']]
            self.assertEqual(execution['context']['output_attribution'],expected)
            self.assertEqual(output['input_hash'],digest(execution['context']))
            self.assertEqual(execution['receipt']['execution_mode'],'SYNTHETIC')

    def test_crash_reopen_resumes_only_missing_calls(self):
        interrupted=SyntheticWorkflowTransport(fail_on=6)
        with self.assertRaises(ProviderBlocked):self.run_workflow(self.provider(interrupted))
        self.assertEqual(self.store.jobs()[0]['status'],'BLOCKED')
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM artifacts WHERE kind='executions'").fetchone()[0],5)
        core_hash=self.store.get(self.race['race_id'],'core','pre-v1')['content_hash']
        self.store.close()
        self.store=Store(Path(self.temp.name)/'private',now=self.clock)
        result=self.run_workflow()
        self.assertEqual(len(self.transport.calls),16)
        self.assertEqual(len(result['execution_receipts']),21)
        self.assertEqual(self.store.get(self.race['race_id'],'core','pre-v1')['content_hash'],core_hash)

    def test_same_edition_rejects_changed_core_input(self):
        self.run_workflow()
        self.raw['runners'][0]['carried_weight']=56
        self.raw['source']['content_hash']=digest({k:v for k,v in self.raw.items() if k!='source'})
        with self.assertRaisesRegex(ValueError,'CORE_INPUT_CHANGED_USE_NEW_EDITION'):self.run_workflow()
        self.assertEqual(len(self.transport.calls),21)

    def test_synthetic_publication_cannot_be_promoted(self):
        self.run_workflow()
        report=publish_saved(self.store,self.race['race_id'],{},now=self.clock)
        self.assertFalse(report['ready'])
        self.assertTrue(any(e.startswith('EXECUTION_UNPROVEN:') for e in report['errors']))
        self.assertIsNone(self.store.get(self.race['race_id'],'publication','pre-v1'))
        self.assertEqual(self.store.jobs()[0]['status'],'BLOCKED_PUBLICATION')

    def test_publish_missing_saved_inputs_has_explicit_error(self):
        with self.assertRaisesRegex(ValueError,'PUBLICATION_INPUTS_NOT_SAVED'):
            publish_saved(self.store,self.race['race_id'],{},now=self.clock)

    def test_already_saved_publication_is_idempotent_and_rejects_changed_paper(self):
        # Storage-boundary fixture only; this does not execute or pass a real
        # publication gate and is never included in independent execution counts.
        paper={'manifest_hash':'SYNTHETIC-storage-test-only','images':[]}
        gate={'ready':True,'test_fixture_only':True}
        self.store.save(self.race['race_id'],'publication','pre-v1',
                        {'paper':paper,'gate':gate,'published_at':'2026-11-12T09:00:00+00:00'})
        self.assertEqual(publish_saved(self.store,self.race['race_id'],paper,now=self.clock),gate)
        with self.assertRaisesRegex(ValueError,'PUBLISHED_PAPER_CHANGED_USE_NEW_EDITION'):
            publish_saved(self.store,self.race['race_id'],{**paper,'images':['changed']},now=self.clock)

    def test_response_id_collision_with_cached_execution_is_rejected(self):
        interrupted=SyntheticWorkflowTransport(fail_on=6)
        with self.assertRaises(ProviderBlocked):self.run_workflow(self.provider(interrupted))
        old_id=self.store.get(self.race['race_id'],'executions',
                              'pre-v1-initial-'+self.race['required_forecasters'][0])['payload']['receipt']['execution_id']
        def reused_id(body,timeout):
            response=self.transport(body,timeout);response['id']=old_id
            return response
        with self.assertRaisesRegex(ValueError,'DUPLICATE_EXECUTION_ID_DIFFERENT_OUTPUT'):
            self.run_workflow(self.provider(reused_id))
        self.assertEqual(self.store.jobs()[0]['status'],'BLOCKED')

    def test_unconfigured_provider_block_is_persisted_by_runtime(self):
        paths={}
        for label,value in [('card',self.card),('characters',self.snapshot),('engine_input',self.raw)]:
            path=Path(self.temp.name)/(label+'.json');path.write_text(json.dumps(value),encoding='utf-8')
            paths[label]=str(path)
        with patch.dict('os.environ',{'PRISM_OPENAI_MODEL':'explicit-test-model'},clear=True):
            result=execute_job({'race_id':self.race['race_id'],**paths,'render':False},self.store,now=self.clock)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(self.store.jobs()[0]['status'],'BLOCKED')
        self.assertIn('OPENAI_API_KEY',result['reason'])
        self.assertIsNotNone(self.store.get(self.race['race_id'],'core','pre-v1'))
        self.assertIsNone(self.store.get(self.race['race_id'],'bundle','pre-v1'))

    def test_mismatched_core_runner_identity_is_blocked_before_api(self):
        self.raw['runners'][0]['horse_id']='wrong-horse'
        self.raw['source']['content_hash']=digest({k:v for k,v in self.raw.items() if k!='source'})
        with self.assertRaisesRegex(ValueError,'CORE_RUNNER_IDENTITY_MISMATCH'):self.run_workflow()
        self.assertEqual(self.transport.calls,[])

    def test_stale_draw_and_wrong_race_time_are_blocked_before_api(self):
        original=deepcopy(self.raw)
        for mutate,error in [
            (lambda raw:raw['runners'][0].update(frame_no=8),'CORE_OFFICIAL_DRAW_MISMATCH'),
            (lambda raw:raw['race'].update(cutoff='2026-11-13T16:00:00+09:00'),'CORE_RACE_START_MISMATCH'),
            (lambda raw:raw['race'].update(declaration_stage='ENTRIES_CONFIRMED'),'CORE_DECLARATION_STAGE_MISMATCH')]:
            self.raw=deepcopy(original);mutate(self.raw)
            self.raw['source']['content_hash']=digest({k:v for k,v in self.raw.items() if k!='source'})
            with self.subTest(error=error),self.assertRaisesRegex(ValueError,error):self.run_workflow()
        self.assertEqual(self.transport.calls,[])

    def test_reader_lists_saved_synthetic_bundle_without_claiming_publication(self):
        self.run_workflow()
        html=archive(self.store.directory)
        self.assertIn('SYNTHETIC-WORKFLOW',html)
        self.assertIn('bundle / pre-v1',html)
        self.assertNotIn('publication / pre-v1',html)

    def test_deadline_crossed_during_api_retains_receipt_and_stops_next_stage(self):
        def slow_transport(body,timeout):
            response=self.transport(body,timeout)
            self.clock.at+=timedelta(days=1)
            return response
        with self.assertRaisesRegex(ValueError,'DEADLINE_PASSED_DURING_EXECUTION'):
            self.run_workflow(self.provider(slow_transport))
        self.assertEqual(len(self.transport.calls),1)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM artifacts WHERE kind='executions'").fetchone()[0],1)
        self.assertIsNone(self.store.get(self.race['race_id'],'bundle','pre-v1'))
        self.assertEqual(self.store.jobs()[0]['status'],'BLOCKED')

    def test_relative_data_directory_remains_readable_after_restart(self):
        self.store.close()
        self.store=Store(os.path.relpath(Path(self.temp.name)/'private'),now=self.clock)
        self.assertTrue(self.store.directory.is_absolute())
        self.run_workflow()
        self.assertIn('bundle / pre-v1',archive(self.store.directory.resolve()))


if __name__=='__main__':unittest.main()
