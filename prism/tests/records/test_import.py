"""Synthetic importer invariants; no invented real discussions or PRE proofs."""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from build_entity_database import run,horse_source_key,jockey_source_key,load_inputs,import_rows
from prism_engine.recovered_observations import extract_nar_candidate
from prism_records import RecordStore


def race(date,identifier):
    return {'race_id':identifier,'date':date,'start':'1000','venue':'TEST','number':1,'authority':'NAR',
            'surface':'DIRT','distance':1200,'direction':'RIGHT','title':'SYNTHETIC','source':'PRIVATE_SOURCE',
            'source_kind':'NAR_OFFICIAL_MONTHLY_CSV',
            'entrants':[{'number':n,'frame':n,'name':'SAME_SYNTHETIC_NAME','identity':f'NAR|SYNTHETIC|BIRTH{n}',
                         'identity_quality':'SYNTHETIC_COMPOSITE','career':{},'age':3,'weight':55}
                        for n in (1,2)],
            'results':[{'number':1,'rank':1,'status':'1'},{'number':2,'rank':2,'status':'2'}],'win_payouts':{'1':350}}


def inputs(root):
    january=[race('20260101','SYNTHETIC_JAN')];bootstrap=[race('20251231','SYNTHETIC_DEC')]
    raw=root/'raw';raw.mkdir();hold=root/'hold';hold.mkdir()
    rows=[{'競走年月日':'20260101','競馬場':'TEST','レース番号':'1','馬番':str(n),'枠番':str(n),'負担重量':'55',
           '馬体重':'480','馬体重増減':'+2','騎手名':'SYNTHETIC_RIDER','騎手成績':'1-2-3-4',
           '性':'牡','齢':'3','父馬名':'SYNTHETIC_SIRE','馬主氏名':'DO_NOT_IMPORT_OWNER',
           '着順':str(n),'タイム':'1:10.0','上がり3F':'36.0','人気':'1'} for n in (1,2)]
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with ZipFile(raw/'nar_202601_official.zip','w') as zipped:zipped.writestr('synthetic_horselist.csv',stream.getvalue())
    for row in rows:
        candidate=extract_nar_candidate(row,'SYNTHETIC_JAN','RECOVERED_NAR_OFFICIAL_MONTHLY_202601')
        (hold/(row['馬番']+'.json')).write_text(json.dumps(candidate,ensure_ascii=False))
    jan=root/'january.json';dec=root/'bootstrap.json'
    jan.write_text(json.dumps(january,ensure_ascii=False));dec.write_text(json.dumps(bootstrap,ensure_ascii=False))
    return jan,dec,raw,hold,root/'records.sqlite'


class ImportTests(unittest.TestCase):
    def test_counts_separation_and_no_name_only_horse_merge(self):
        with TemporaryDirectory() as folder:
            args=inputs(Path(folder));summary=run(*args)
            self.assertEqual(summary['counts']['horses_provisional'],2)
            self.assertEqual(summary['counts']['jockey_name_buckets_provisional'],1)
            self.assertEqual(summary['counts']['races'],2);self.assertEqual(summary['counts']['entries'],4)
            self.assertEqual(summary['counts']['quarantined_observations'],2)
            self.assertEqual(summary['counts']['extra_source_detail_observations'],2)
            self.assertFalse(summary['mock_discussion_evaluations_created'])
            store=RecordStore(args[-1],read_only=True)
            try:
                self.assertEqual(store.summary()['counts']['assessments'],0)
                details=json.loads(store.connection.execute("SELECT details_json FROM entries WHERE race_id='SYNTHETIC_JAN' AND horse_no=1").fetchone()[0])
                self.assertEqual(details['post_result']['rank'],1)
                self.assertEqual(details['post_result']['recorded_win_payout_per_100_yen'],350)
                self.assertNotIn('rank',details['reconstructed_pre'])
                observations=[json.loads(r[0]) for r in store.connection.execute('SELECT payload_json FROM observations')]
                self.assertNotIn('DO_NOT_IMPORT_OWNER',str(observations))
                self.assertTrue(all(r[0] is None for r in store.connection.execute('SELECT available_at FROM observations')))
            finally:store.close()

    def test_same_import_is_byte_identical_and_changed_source_is_rejected(self):
        with TemporaryDirectory() as folder:
            args=inputs(Path(folder));first=run(*args);before=args[-1].read_bytes()
            self.assertEqual(first,run(*args));self.assertEqual(before,args[-1].read_bytes())
            jan,dec,raw,hold,db=args
            data=json.loads(jan.read_text());data[0]['title']='DIFFERENT';jan.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'changed source'):run(*args)
            self.assertEqual(before,db.read_bytes())

    def test_hold_content_tamper_even_if_rehashed_is_rejected(self):
        with TemporaryDirectory() as folder:
            args=inputs(Path(folder));path=args[3]/'1.json';value=json.loads(path.read_text())
            from prism_engine.contracts import digest
            value['observations']['body_weight_kg']=999
            value['candidate_hash']=digest({k:v for k,v in value.items() if k!='candidate_hash'})
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'hold/raw'):run(*args)
            self.assertFalse(args[-1].exists())

    def test_partial_hold_coverage_never_creates_database(self):
        with TemporaryDirectory() as folder:
            args=inputs(Path(folder));(args[3]/'2.json').unlink()
            with self.assertRaisesRegex(ValueError,'hold and January'):run(*args)
            self.assertFalse(args[-1].exists())

    def test_transaction_rolls_back_on_late_entity_conflict(self):
        with TemporaryDirectory() as folder:
            args=inputs(Path(folder));dec,jan,raw,held,hashes=load_inputs(*args[:4])
            broken=deepcopy(jan);broken[0]['entrants'][1]['name']='CONFLICT_SAME_ID'
            with self.assertRaisesRegex(ValueError,'immutable entity'):import_rows(args[-1],dec,broken,raw,held,hashes)
            store=RecordStore(args[-1],read_only=True)
            try:
                self.assertEqual(store.summary()['counts']['entries'],0)
                self.assertEqual(store.summary()['counts']['horses'],0)
            finally:store.close()

    def test_exact_rider_names_and_authorities_are_not_merged(self):
        self.assertNotEqual(jockey_source_key('JRA','SAME'),jockey_source_key('NAR','SAME'))
        self.assertNotEqual(jockey_source_key('JRA','SAME'),jockey_source_key('JRA','SAME '))
        self.assertNotEqual(horse_source_key({'identity':'NAR|same|birth1'}),horse_source_key({'identity':'NAR|same|birth2'}))

    def test_aggregate_receipt_has_no_individual_names_or_raw_records(self):
        with TemporaryDirectory() as folder:
            summary=run(*inputs(Path(folder)));value=json.dumps(summary)
            self.assertNotIn('SAME_SYNTHETIC_NAME',value);self.assertNotIn('SYNTHETIC_RIDER',value)
            self.assertNotIn('DO_NOT_IMPORT_OWNER',value);self.assertNotIn('PRIVATE_SOURCE',value)

    def test_invalid_existing_database_is_preserved_without_writes(self):
        with TemporaryDirectory() as folder:
            args=inputs(Path(folder));args[-1].write_bytes(b'not-a-valid-sqlite')
            before=args[-1].read_bytes()
            with self.assertRaisesRegex(ValueError,'preserved without writes'):run(*args)
            self.assertEqual(args[-1].read_bytes(),before)

    def test_unrelated_existing_database_is_preserved_without_writes(self):
        with TemporaryDirectory() as folder:
            args=inputs(Path(folder));connection=sqlite3.connect(args[-1])
            connection.execute('CREATE TABLE unrelated(value TEXT)');connection.commit();connection.close()
            before=args[-1].read_bytes()
            with self.assertRaisesRegex(ValueError,'preserved without writes'):run(*args)
            self.assertEqual(args[-1].read_bytes(),before)


if __name__=='__main__':unittest.main()
