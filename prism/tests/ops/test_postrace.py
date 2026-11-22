"""Synthetic persistence/settlement integration; no real model executions."""
from copy import deepcopy
import json
from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'src'), str(Path(__file__).resolve().parent)]
from prism_engine.contracts import digest
from prism_ops.characters import get_character
from prism_ops.postrace import settle_saved, settle_synthetic_saved, reflect_saved, _node
from prism_ops.provider import OpenAIProvider
from prism_ops.store import Store
from test_characters import snapshot_fixture


def saved_fixture(store):
    snapshot = snapshot_fixture()
    character = get_character(snapshot, 'notion-ability')
    race = {'race_id':'SYNTHETIC-POST', 'race_name':'架空精算検証', 'authority':'JRA',
            'start_at':'2026-11-14T15:00:00+09:00',
            'runners':[{'horse_id':'h1','horse_no':1,'name':'架空馬A','frame_no':1},
                       {'horse_id':'h2','horse_no':2,'name':'架空馬B','frame_no':2}],
            'character_snapshot_hash':snapshot['snapshot_hash'],
            'required_forecasters':['notion-ability'], 'source_refs':['synthetic-fixture']}
    payload = {'diagnoses':[{'horse_id':h,'reason':'架空根拠 ' + h} for h in ('h1','h2')],
               'picks':[{'horse_id':'h1','mark':'◎','reason':'架空印'}],
               'tickets':[{'type':'WIN','horse_nos':[1],'stake_yen':200}],
               'skip_reason':'','change_reason':'架空検証：一次予想を維持'}
    context = {'race_id':race['race_id'],'runners':race['runners'],
               'character_snapshot_hash':snapshot['snapshot_hash']}
    def transport(body, timeout):
        stage = json.loads(body['input'])['stage']
        return {'id':'resp_synthetic_' + stage, 'status':'completed', 'output':[
            {'type':'message','content':[{'type':'output_text','text':json.dumps(payload)}]}]}
    provider = OpenAIProvider(model='explicit-synthetic-only', transport=transport,
                              now=lambda:'2026-11-13T12:00:00+09:00')
    initial = provider.predict(context,character,stage='PRELIMINARY')
    final = provider.predict(context,character,stage='FINAL')
    for evidence in (initial,final):
        evidence['persisted_at']='2026-11-13T13:00:00+09:00'
    bundle={'race':race,'preliminary':{'notion-ability':initial['output']},
            'discussions':[], 'final':{'notion-ability':final['output']},
            'core_prediction':{'win':{'h1':.6,'h2':.4}}}
    store.save(race['race_id'],'bundle','pre-v1',bundle)
    store.save(race['race_id'],'receipts','pre-v1',
               {e['receipt']['execution_id']:e for e in (initial,final)})
    publication={'bundle_hash':digest(bundle),'mode':'SYNTHETIC',
                 'published_at':'2026-11-13T20:00:00+09:00','gate':{'ready':False,'errors':['SYNTHETIC']}}
    store.save(race['race_id'],'synthetic-publication','pre-v1',publication)
    return race, bundle, publication


def result_fixture():
    return {'mode':'SYNTHETIC','race_id':'SYNTHETIC-POST','official_source':'SYNTHETIC ONLY',
            'published_at':'2026-11-14T16:00:00+09:00','status':'FINAL',
            'complete_payouts':True,'complete_bet_types':['WIN'],
            'payouts':[{'type':'WIN','horse_nos':[1],'payout_per_100_yen':350}]}


class PostraceTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.clock=['2026-11-13T20:00:00+09:00']
        self.store=Store(self.directory.name,now=lambda:self.clock[0])
        self.race,self.bundle,self.publication=saved_fixture(self.store)
        self.clock[0]='2026-11-14T16:10:00+09:00'

    def tearDown(self):
        self.store.close(); self.directory.cleanup()

    def settle(self,result=None):
        return settle_synthetic_saved(self.store,self.race['race_id'],result or result_fixture(),now=lambda:self.clock[0])

    def test_explicit_synthetic_settlement_keeps_zero_official_counts_and_records_reviews(self):
        before=self.store.get(self.race['race_id'],'bundle','pre-v1')['content_hash']
        response=self.settle()
        self.assertEqual(response['official_settlements'],0)
        self.assertEqual(response['settlement']['summary'][0]['profit_yen'],500)
        self.assertEqual(response['settlement']['mode'],'SYNTHETIC')
        review=response['reviews'][0]
        self.assertAlmostEqual(review['official_outcome']['core_brier'],.32)
        self.assertEqual(review['ai_reflection_execution'],'NOT_EXECUTED')
        self.assertEqual(review['status'],'REVIEW_RECORDED_NOT_TRAINED')
        self.assertFalse(response['learning_candidates'][0]['training_executed'])
        self.assertFalse(response['learning_candidates'][0]['adopted'])
        self.assertEqual(before,self.store.get(self.race['race_id'],'bundle','pre-v1')['content_hash'])
        forecast=self.store.get(self.race['race_id'],'settlement-forecast','pre-v1')['payload']
        self.assertFalse(forecast['records'][0]['independent_execution'])
        self.assertEqual(forecast['records'][0]['mode'],'single_model_simulation')

    def test_repeated_settlement_is_idempotent_and_corrections_have_distinct_ids(self):
        first=self.settle()
        self.clock[0]='2026-11-14T17:10:00+09:00'
        second=self.settle()
        self.assertFalse(first['cache_hit']);self.assertTrue(second['cache_hit'])
        self.assertEqual(first['settlement'],second['settlement'])
        self.assertEqual(first['reviews'],second['reviews'])
        result=result_fixture();result['payouts'][0]['payout_per_100_yen']=400
        result.update(revision=2,correction_of=first['settlement']['result_sha256'])
        corrected=self.settle(result)
        self.assertNotEqual(first['settlement']['settlement_id'],corrected['settlement']['settlement_id'])
        rows=self.store.db.execute("SELECT count(*) FROM artifacts WHERE kind='settlement'").fetchone()[0]
        self.assertEqual(rows,2)

    def test_no_real_settlement_from_synthetic_publication_or_missing_publication(self):
        with self.assertRaisesRegex(ValueError,'PUBLICATION_MISSING'):
            settle_saved(self.store,self.race['race_id'],result_fixture(),now=lambda:self.clock[0])
        self.clock[0]='2026-11-13T20:00:00+09:00'
        self.store.save(self.race['race_id'],'publication','pre-v1',self.publication)
        self.clock[0]='2026-11-14T16:10:00+09:00'
        with self.assertRaisesRegex(ValueError,'ACCEPTED_PUBLICATION'):
            settle_saved(self.store,self.race['race_id'],result_fixture(),now=lambda:self.clock[0])

    def test_synthetic_path_never_accepts_official_result_or_future_result(self):
        result=result_fixture();result['mode']='OFFICIAL'
        with self.assertRaisesRegex(ValueError,'MISMATCH'):
            self.settle(result)
        result=result_fixture();result['published_at']='2026-11-14T19:00:00+09:00'
        with self.assertRaisesRegex(ValueError,'provenance'):
            self.settle(result)

    def test_bad_bundle_binding_and_missing_receipts_fail(self):
        self.store.save(self.race['race_id'],'synthetic-publication','bad-v1',
                        {**self.publication,'bundle_hash':'0'*64})
        self.store.save(self.race['race_id'],'bundle','bad-v1',self.bundle)
        self.store.save(self.race['race_id'],'receipts','bad-v1',{})
        with self.assertRaisesRegex(ValueError,'BUNDLE_BINDING'):
            settle_synthetic_saved(self.store,self.race['race_id'],result_fixture(),edition='bad-v1',now=lambda:self.clock[0])
        with self.assertRaisesRegex(ValueError,'PUBLICATION_MISSING'):
            settle_synthetic_saved(self.store,self.race['race_id'],result_fixture(),edition='not-saved',now=lambda:self.clock[0])
        self.clock[0]='2026-11-13T20:00:00+09:00'
        self.store.save(self.race['race_id'],'synthetic-publication','empty-receipts',self.publication)
        self.store.save(self.race['race_id'],'bundle','empty-receipts',self.bundle)
        self.store.save(self.race['race_id'],'receipts','empty-receipts',{})
        self.clock[0]='2026-11-14T16:10:00+09:00'
        with self.assertRaisesRegex(ValueError,'RECEIPT_BINDING'):
            settle_synthetic_saved(self.store,self.race['race_id'],result_fixture(),edition='empty-receipts',now=lambda:self.clock[0])

    def test_missing_complete_win_outcome_is_unknown_not_invented_brier(self):
        result=result_fixture();result['payouts']=[];result['refunds']=[{'type':'WIN','horse_nos':[1]}]
        response=self.settle(result)
        self.assertEqual(response['reviews'][0]['official_outcome']['status'],'UNKNOWN')
        self.assertIsNone(response['reviews'][0]['official_outcome']['core_brier'])



    def test_official_parser_hash_matches_node_digest_contract(self):
        from prism_ops.official import parse_nar_result
        from test_official import PAYOUT, RESULT_URL
        body=PAYOUT.encode('utf-8')
        path=Path(self.directory.name)/'synthetic-payout.html'
        path.write_bytes(body)
        snapshot={'authority':'NAR','official_url':RESULT_URL,'body_path':str(path),
                  'captured_at':'2026-11-13T08:00:00Z','source_sha256':sha256(body).hexdigest(),
                  'encoding':'utf-8','mode':'SYNTHETIC'}
        parsed=parse_nar_result(snapshot,expected_date='2026-11-13',expected_venue='27',expected_race_no=11)
        expected=_node({'operation':'result_digest','result':parsed})['normalized_sha256']
        self.assertEqual(parsed['source_snapshot']['normalized_sha256'],expected)
        self.assertIsNone(parsed['published_at'])
        self.assertEqual(parsed['mode'],'SYNTHETIC')

    def test_backdated_publication_with_post_start_durable_save_is_rejected(self):
        self.store.save(self.race['race_id'],'bundle','late-v1',self.bundle)
        receipts=self.store.get(self.race['race_id'],'receipts','pre-v1')['payload']
        self.store.save(self.race['race_id'],'receipts','late-v1',receipts)
        self.store.save(self.race['race_id'],'synthetic-publication','late-v1',self.publication)
        with self.assertRaisesRegex(ValueError,'PERSISTED_AFTER_START'):
            settle_synthetic_saved(self.store,self.race['race_id'],result_fixture(),edition='late-v1',now=lambda:self.clock[0])

    def test_reflection_requires_real_accepted_publication_and_official_settlement(self):
        with self.assertRaisesRegex(ValueError,'PUBLICATION_MISSING'):
            reflect_saved(self.store,self.race['race_id'],OpenAIProvider(),now=lambda:self.clock[0])
        with patch('prism_ops.postrace._validate_saved',return_value=(self.publication,self.bundle,{})):
            with self.assertRaisesRegex(ValueError,'OFFICIAL_SETTLEMENT_REQUIRED'):
                reflect_saved(self.store,self.race['race_id'],OpenAIProvider(),now=lambda:self.clock[0])

    def reflection_harness(self):
        # A scoped stored-state harness, never a real publication or execution.
        response=self.settle()
        saved=response['settlement']
        fake={**saved,'official_settlements':1}
        self.store.save(self.race['race_id'],'settlement','synthetic-reflection-harness',fake)
        self.store.save(self.race['race_id'],'characters','pre-v1',snapshot_fixture())
        return self.store.get(self.race['race_id'],'settlement','synthetic-reflection-harness')

    def test_reflection_auth_failure_preserves_settlement_and_records_no_success(self):
        original=self.reflection_harness()
        with patch('prism_ops.postrace._validate_saved',return_value=(self.publication,self.bundle,{})):
            with patch.dict('os.environ',{},clear=True):
                response=reflect_saved(self.store,self.race['race_id'],OpenAIProvider(),now=lambda:self.clock[0])
        self.assertEqual(response['independent_reflections'],0)
        self.assertEqual(len(response['blocked']),1)
        self.assertFalse(response['training_executed'])
        self.assertTrue(response['official_settlement_preserved'])
        self.assertEqual(original['content_hash'],self.store.get(self.race['race_id'],'settlement','synthetic-reflection-harness')['content_hash'])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM artifacts WHERE kind='ai-review'").fetchone()[0],0)

    def test_injected_synthetic_reflection_cannot_become_independent_ai_review(self):
        self.reflection_harness()
        def transport(body,timeout):
            payload={'text':'SYNTHETIC reflection','evidence_refs':['original_final'],'stance':'CHALLENGE','responds_to':None}
            return {'id':'resp_synthetic_post','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(payload)}]}]}
        provider=OpenAIProvider(model='explicit-synthetic',transport=transport,now=lambda:self.clock[0])
        with patch('prism_ops.postrace._validate_saved',return_value=(self.publication,self.bundle,{})):
            response=reflect_saved(self.store,self.race['race_id'],provider,now=lambda:self.clock[0])
        self.assertEqual(response['independent_reflections'],0)
        self.assertIn('independent',response['blocked'][0]['reason'])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM artifacts WHERE kind='ai-review'").fetchone()[0],0)


if __name__=='__main__':
    unittest.main()
