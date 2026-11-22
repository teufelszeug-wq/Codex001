"""Watch integration uses injected SYNTHETIC sources; no official GET occurs."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from prism_engine.contracts import digest
from prism_ops.acquisition import prepare_watch
from prism_ops.characters import build_character_snapshot
from prism_ops.runtime import tick
from prism_ops.store import Store


def watch_evidence():
    return {'h'+str(i):{'horse_id':'h'+str(i),'carried_weight':55,
                'source_url':'https://www.jra.go.jp/SYNTHETIC-evidence',
                'available_at':'2026-11-11T09:00:00+00:00',
                'history':[{'occurred_at':'2026-11-01T10:00:00+09:00',
                            'available_at':'2026-11-01T11:00:00+09:00','performance_score':65-i,
                            'distance_m':1600,'surface':'TURF','direction':'LEFT',
                            'class_rating':50,'venue':'TEST'}]} for i in (1,2)}


class SyntheticWatchSource:
    def __init__(self):
        self.fetch_calls=0;self.parse_calls=0
        self.stage='ENTRIES_CONFIRMED'
        self.captured_at='2026-11-12T08:00:00+00:00'
        self.source_sha256=digest({'fixture':'SYNTHETIC entries HTML bytes'})

    def fetch(self,url,directory):
        self.fetch_calls+=1
        return {'authority':'JRA','official_url':url,'captured_at':self.captured_at,
                'source_sha256':self.source_sha256,'mode':'LIVE_FETCH'}

    def parse(self,snapshot,**kwargs):
        self.parse_calls+=1
        drawn=self.stage=='DRAW_CONFIRMED'
        runners=[{'horse_id':'h'+str(i),'horse_name':'架空馬'+str(i),
                  'horse_no':i if drawn else None,'frame_no':i if drawn else None,
                  'status':'DECLARED'} for i in (1,2)]
        return {'schema':'prism.official_racecard/v2','race_id':'SYNTHETIC-WATCH',
                'authority':'JRA','race_name':'架空監視競走','declaration_stage':self.stage,
                'source_verified':True,'mode':'LIVE_FETCH','captured_at':snapshot['captured_at'],
                'off_at':'2026-11-13T15:00:00+09:00','start_at':'2026-11-13T15:00:00+09:00',
                'official_url':snapshot['official_url'],'source_sha256':snapshot['source_sha256'],
                'source_evidence':snapshot,'runners':runners,'active_runners':runners}


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.now=lambda:'2026-11-12T09:00:00+00:00'
        self.store=Store(self.root/'private',now=self.now)
        self.characters=self.root/'characters.json'
        self.characters.write_text(json.dumps({'records':[{'synthetic_fixture_only':True}]}),encoding='utf-8')
        self.evidence=self.root/'evidence.json'
        self.evidence.write_text(json.dumps(watch_evidence()),encoding='utf-8')
        self.watch={'race_id':'SYNTHETIC-WATCH','authority':'JRA',
                    'official_url':'https://www.jra.go.jp/JRADB/SYNTHETIC-TEST-ONLY',
                    'expected_date':'2026-11-13','expected_venue':'TEST','expected_race_no':11,
                    'expected_race_name':'架空監視競走','characters':str(self.characters),
                    'evidence':str(self.evidence),'engine_parameters':{'venue':'TEST','surface':'TURF',
                        'distance_m':1600,'direction':'LEFT','class_rating':50,'barrier_count':2}}
        self.source=SyntheticWatchSource()

    def tearDown(self):
        self.store.close();self.temp.cleanup()

    def prepare(self,watch=None):
        return prepare_watch(watch or self.watch,self.store,now=self.now,
                             fetcher=self.source.fetch,parser=self.source.parse)

    def test_entries_prepare_frozen_job_without_invented_numbers_or_live_claim(self):
        job=self.prepare()
        self.assertTrue(job['edition'].startswith('pre-entries-'))
        card=json.loads(Path(job['card']).read_text())
        raw=json.loads(Path(job['engine_input']).read_text())
        self.assertEqual(raw['race']['declaration_stage'],'ENTRIES_CONFIRMED')
        self.assertTrue(all(r['horse_no'] is None and r['frame_no'] is None and r['barrier_no'] is None
                            for r in raw['runners']))
        self.assertEqual(raw['mode'],'SYNTHETIC')
        self.assertFalse(card['source_verified'])
        self.assertFalse(job['official_fetch_executed'])
        self.assertNotEqual(job['characters'],str(self.characters))
        self.assertTrue(Path(job['characters']).is_file())

    def test_identical_source_reuses_original_capture_and_input_bytes_after_restart(self):
        first=self.prepare()
        first_raw=Path(first['engine_input']).read_bytes()
        self.source.captured_at='2026-11-12T08:30:00+00:00'
        self.store.close();self.store=Store(self.root/'private',now=self.now)
        second=self.prepare()
        self.assertEqual(first,second)
        self.assertEqual(Path(second['engine_input']).read_bytes(),first_raw)
        self.assertEqual(self.source.fetch_calls,2)
        self.assertEqual(self.source.parse_calls,1)
        self.assertEqual(json.loads(first_raw)['source']['available_at'],'2026-11-12T08:00:00+00:00')

    def test_draw_update_creates_distinct_edition_and_preserves_entries(self):
        entries=self.prepare()
        entries_bytes=Path(entries['engine_input']).read_bytes()
        self.source.stage='DRAW_CONFIRMED'
        self.source.source_sha256=digest({'fixture':'SYNTHETIC drawn HTML bytes'})
        draw=self.prepare()
        self.assertTrue(draw['edition'].startswith('pre-draw-'))
        self.assertNotEqual(entries['edition'],draw['edition'])
        self.assertEqual(Path(entries['engine_input']).read_bytes(),entries_bytes)
        self.assertEqual([r['horse_no'] for r in json.loads(Path(draw['engine_input']).read_text())['runners']],[1,2])

    def test_changed_evidence_uses_new_input_edition_without_reparsing_same_source(self):
        first=self.prepare()
        changed=watch_evidence();changed['h1']['carried_weight']=56
        self.evidence.write_text(json.dumps(changed),encoding='utf-8')
        second=self.prepare()
        self.assertNotEqual(first['edition'],second['edition'])
        self.assertEqual(self.source.parse_calls,1)

    def test_missing_horse_evidence_is_persisted_blocked_without_prediction(self):
        evidence=watch_evidence();del evidence['h2']
        self.evidence.write_text(json.dumps(evidence),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'BLOCKED_SOURCE_EVIDENCE'):self.prepare()
        self.assertEqual(self.store.jobs()[0]['status'],'BLOCKED')
        detail=json.loads(self.store.jobs()[0]['detail'])
        self.assertEqual(detail['official_publications'],0)
        self.assertIn('complete evidence required',detail['reason'])

    def test_not_before_does_not_fetch_or_parse(self):
        result=self.prepare({**self.watch,'not_before':'2026-11-12T10:00:00+00:00'})
        self.assertEqual(result['status'],'NOT_DUE')
        self.assertEqual(self.source.fetch_calls,0)

    def test_worker_option_changes_reuse_evidence_without_stale_job_settings(self):
        first=self.prepare()
        second=self.prepare({**self.watch,'render':False,'not_before':'2026-11-12T08:30:00+00:00'})
        self.assertEqual(first['edition'],second['edition'])
        self.assertEqual(first['engine_input'],second['engine_input'])
        self.assertFalse(second['render'])
        self.assertEqual(second['due_at'],'2026-11-12T08:30:00+00:00')
        self.assertEqual(self.source.parse_calls,1)

    def test_runtime_watch_keeps_injected_source_blocked_from_official_execution(self):
        characters=build_character_snapshot([
            {'agent_id':'SYNTHETIC-specialist','name':'架空監視担当','role':'specialist',
             'configuration':{'instruction':'SYNTHETIC fixture only'},
             'source_page_url':'https://www.notion.so/'+'b'*32}],
            source_url='https://www.notion.so/'+'a'*32,captured_at='2026-11-12T08:00:00+00:00')
        self.characters.write_text(json.dumps(characters),encoding='utf-8')
        class NoApiProvider:
            calls=0
            def predict(provider,*args,**kwargs):
                provider.calls+=1
                raise AssertionError('Synthetic acquisition must not start official prediction')
        provider=NoApiProvider()
        def injected_prepare(watch,store,*,now):
            return prepare_watch(watch,store,now=now,fetcher=self.source.fetch,parser=self.source.parse)
        with patch('prism_ops.acquisition.prepare_watch',side_effect=injected_prepare):
            entries=tick({'watches':[self.watch]},self.store,provider=provider,now=self.now)
            self.source.stage='DRAW_CONFIRMED'
            self.source.source_sha256=digest({'fixture':'SYNTHETIC runtime draw bytes'})
            draw=tick({'watches':[self.watch]},self.store,provider=provider,now=self.now)
        self.assertEqual(entries['results'][0]['status'],'BLOCKED')
        self.assertIn('BLOCKED_OFFICIAL_IDENTITY',entries['results'][0]['reason'])
        self.assertEqual(draw['results'][0]['status'],'BLOCKED')
        self.assertEqual(provider.calls,0)
        prepared=self.store.db.execute("SELECT path FROM artifacts WHERE kind='watch-inputs'").fetchall()
        self.assertEqual(len(prepared),2)
        jobs=[json.loads(Path(row[0]).read_text()) for row in prepared]
        self.assertEqual({job['declaration_stage'] for job in jobs},{'ENTRIES_CONFIRMED','DRAW_CONFIRMED'})
        self.assertTrue(all(not job['official_fetch_executed'] for job in jobs))
        self.assertFalse(self.store.db.execute("SELECT 1 FROM artifacts WHERE kind='publication'").fetchall())

    def test_runtime_waits_without_acquisition_or_api_calls(self):
        watch={**self.watch,'not_before':'2026-11-12T10:00:00+00:00'}
        def injected_prepare(value,store,*,now):
            return prepare_watch(value,store,now=now,fetcher=self.source.fetch,parser=self.source.parse)
        with patch('prism_ops.acquisition.prepare_watch',side_effect=injected_prepare):
            result=tick({'watches':[watch]},self.store,now=self.now)
        self.assertEqual(result['results'][0]['status'],'NOT_DUE')
        self.assertEqual(self.source.fetch_calls,0)

    def test_wrong_official_identity_and_missing_jra_title_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'identity mismatch'):
            self.prepare({**self.watch,'race_id':'OTHER-RACE'})
        missing=deepcopy(self.watch);del missing['expected_race_name']
        with self.assertRaisesRegex(ValueError,'expected_race_name'):self.prepare(missing)

    def test_untrusted_watch_url_is_rejected_before_fetch(self):
        with self.assertRaises(ValueError):
            self.prepare({**self.watch,'official_url':'https://example.com/official'})
        self.assertEqual(self.source.fetch_calls,0)


if __name__=='__main__':unittest.main()
