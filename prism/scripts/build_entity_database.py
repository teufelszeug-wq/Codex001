"""Import recovered horse/jockey records into a private, immutable SQLite store.

Only aggregate receipts belong in the public repository. Source-scoped identities
and exact-name rider buckets are provisional, never canonical identity proof.
"""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import io
import json
from pathlib import Path
import sqlite3
import sys
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from prism_engine.contracts import digest
from prism_engine.recovered_observations import extract_nar_candidate,extract_jra_candidate

RECEIPT_KEY='recovered-dec2025-jan2026-entities-v1'
NAR_DETAIL_FIELDS=('性','齢','毛色','生年月日','父馬名','母馬名','母父馬名','騎手所属','調教師',
                   '調教師所属','生産牧場名','全成績','ダート左成績','ダート右成績','当競馬場成績',
                   'うち当距離成績','最高タイム','最高タイム良馬場')


def canonical(rows):
    return [{k:v for k,v in race.items() if k!='source'} for race in rows]


def horse_source_key(horse):
    identity=horse.get('identity')
    if not isinstance(identity,str) or not identity.strip():raise ValueError('source-scoped horse identity required')
    return 'RECOVERED_CANONICAL:'+identity


def jockey_source_key(authority,exact_name):
    if not isinstance(exact_name,str) or not exact_name.strip():raise ValueError('nonempty exact rider name required')
    return 'RECOVERED_JAN_RAW:'+authority+':EXACT_NAME:'+exact_name


def raw_candidates(root,january):
    """Regenerate quarantine candidates to verify the previously extracted store."""
    from lxml import html
    root=Path(root);records={};source_hashes=[]
    nar={(r['date'],r['venue'],r['number']):r for r in january if r['authority']=='NAR'}
    jra={str(r['source']).split('jra_racingviewer/')[-1]:r for r in january if r['authority']=='JRA'}
    def add(candidate,authority,exact_name,extra_details,post_details):
        key=(candidate['race_id'],candidate['horse_identity']['horse_no'])
        if key in records:raise ValueError('duplicate raw entrant')
        records[key]={'candidate':candidate,'authority':authority,'exact_jockey_name':exact_name,
                      'extra_source_details':extra_details,'post_source_details':post_details}
    archive=root/'nar_202601_official.zip'
    if nar:
        source_hashes.append(sha256(archive.read_bytes()).hexdigest())
        with ZipFile(archive) as zipped:
            name=next(n for n in zipped.namelist() if n.endswith('_horselist.csv'))
            for row in csv.DictReader(io.StringIO(zipped.read(name).decode('utf-8-sig'))):
                key=(row.get('競走年月日'),row.get('競馬場'),int(row['レース番号']))
                if key in nar:
                    add(extract_nar_candidate(row,nar[key]['race_id'],'RECOVERED_NAR_OFFICIAL_MONTHLY_202601'),
                        'NAR',row.get('騎手名',''),
                        {field:row[field] for field in NAR_DETAIL_FIELDS if isinstance(row.get(field),str) and row[field].strip()},
                        {field:row[field] for field in ('着順','タイム','着差','上がり3F','人気') if isinstance(row.get(field),str) and row[field].strip()})
    for page_key,race in sorted(jra.items()):
        content=(root/'jra_racingviewer'/page_key).read_bytes();source_hashes.append(sha256(content).hexdigest())
        for tr in html.fromstring(content).xpath('//table[contains(@class,"striped")]//tr[td]'):
            elements={td.get('class'):td for td in tr.xpath('./td')}
            cells={name:''.join(td.itertext()).strip() for name,td in elements.items()}
            if not cells.get('num','').isdigit():continue
            alt=' '.join(elements['waku'].xpath('.//img/@alt')) if 'waku' in elements else ''
            add(extract_jra_candidate(cells,race['race_id'],'RECOVERED_JRA_RACING_VIEWER_202601',frame_image_alt=alt),
                'JRA',cells.get('jockey',''),
                {field:cells[field] for field in ('age','trainer') if cells.get(field)},
                {field:cells[field] for field in ('place','time','margin','corner','f_time','pop') if cells.get(field)})
    return records,digest(sorted(source_hashes))


def load_inputs(january_path,bootstrap_path,raw_root,hold_root):
    january=json.loads(Path(january_path).read_text());bootstrap=json.loads(Path(bootstrap_path).read_text())
    if any(not r['date'].startswith('202601') for r in january):raise ValueError('January universe required')
    if any(not r['date'].startswith('202512') for r in bootstrap):raise ValueError('December bootstrap required')
    all_rows=bootstrap+january
    if len({r['race_id'] for r in all_rows})!=len(all_rows):raise ValueError('duplicate race identity')
    expected={(r['race_id'],h['number']) for r in january for h in r['entrants']}
    if len(expected)!=sum(len(r['entrants']) for r in january):raise ValueError('duplicate entrant identity')
    raw,raw_hash=raw_candidates(raw_root,january)
    if set(raw)!=expected:raise ValueError('raw and January entrant coverage mismatch')
    held={}
    for path in sorted(Path(hold_root).glob('*.json')):
        value=json.loads(path.read_text());key=(value['race_id'],value['horse_identity']['horse_no'])
        if key in held or key not in raw:raise ValueError('unexpected or duplicate hold candidate')
        if value.get('candidate_hash')!=digest({k:v for k,v in value.items() if k!='candidate_hash'}):raise ValueError('hold candidate hash mismatch')
        if digest(value)!=digest(raw[key]['candidate']):raise ValueError('hold/raw candidate content mismatch')
        held[key]=value
    if set(held)!=expected:raise ValueError('hold and January entrant coverage mismatch')
    hashes={'january_canonical_hash':digest(canonical(january)),
            'december_canonical_hash':digest(canonical(bootstrap)),
            'raw_source_collection_hash':raw_hash,
            'hold_candidate_collection_hash':digest(sorted(v['candidate_hash'] for v in held.values()))}
    return bootstrap,january,raw,held,hashes


def import_rows(db_path,bootstrap,january,raw,held,source_hashes):
    from prism_records import RecordStore
    source_hash=digest(source_hashes)
    # Replays are read-only: do not execute schema DDL or reopen a damaged target
    # for writes merely because its receipt is missing. The first import alone
    # is permitted to create this database.
    target=Path(db_path)
    if target.exists():
        connection=sqlite3.connect(target.resolve().as_uri()+'?mode=ro',uri=True)
        connection.row_factory=sqlite3.Row
        try:
            if [r[0] for r in connection.execute('PRAGMA quick_check')]!=['ok']:
                raise ValueError('existing database integrity check failed; preserved without writes')
            if connection.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('existing database foreign keys failed')
            previous=connection.execute('SELECT source_hash,summary_json FROM _prism_entity_imports WHERE receipt_key=?',(RECEIPT_KEY,)).fetchone()
            if previous is None:raise ValueError('existing database lacks an import receipt; preserved without writes')
            if previous['source_hash']!=source_hash:raise ValueError('refuse changed source bundle for existing import receipt')
            summary=json.loads(previous['summary_json'])
            if summary.get('receipt_hash')!=digest({k:v for k,v in summary.items() if k!='receipt_hash'}):raise ValueError('import receipt integrity mismatch')
            return summary
        except sqlite3.DatabaseError as exc:
            raise ValueError('existing database is invalid or has no supported import receipt; preserved without writes') from exc
        finally:connection.close()
    store=RecordStore(db_path)
    try:
        with store.transaction():
            store.connection.execute('CREATE TABLE IF NOT EXISTS _prism_entity_imports (receipt_key TEXT PRIMARY KEY,source_hash TEXT NOT NULL,summary_json TEXT NOT NULL)')
            horse_ids=set();jockey_ids=set();entry_ids=set();observation_ids=set();detail_observation_ids=set();race_ids=set();counts=Counter()
            for race in sorted(bootstrap+january,key=lambda r:(r['date'],r['start'],r['race_id'])):
                source_ref='RECOVERED_CANONICAL:'+race['date'][:6]+':'+race['source_kind']
                metadata={'reconstructed_pre':{'stage':'PRE_RECONSTRUCTION','temporal_class':'UNKNOWN_TIMESTAMP',
                          'available_at':None,'values':{k:race[k] for k in ('date','start','venue','number','authority','surface','distance','direction','title')}},
                          'post_result':{'stage':'POST','available_at':None,'win_payouts':race.get('win_payouts',{}),
                                         'source_role':'RESULT_BEARING_EVALUATOR_NOT_PRE_INPUT'},
                          'source_ref':source_ref,'source_record_hash':digest({k:v for k,v in race.items() if k!='source'})}
                store.add_race(race['race_id'],metadata);race_ids.add(race['race_id'])
                results={r['number']:r for r in race.get('results',[])}
                for horse in sorted(race['entrants'],key=lambda h:h['number']):
                    key=(race['race_id'],horse['number']);candidate=held.get(key);raw_row=raw.get(key)
                    profile={'authority':race['authority'],'source_namespace':'RECOVERED_CANONICAL',
                             'identity_quality':horse.get('identity_quality','UNKNOWN'),
                             'canonical_identity_verified':False,'same_name_ambiguity':'UNRESOLVED'}
                    horse_id=store.add_horse(horse_source_key(horse),horse['name'],profile=profile)
                    horse_ids.add(horse_id);jockey_id=None
                    if raw_row is not None and raw_row['exact_jockey_name'].strip():
                        exact_name=raw_row['exact_jockey_name']
                        jockey_id=store.add_jockey(jockey_source_key(race['authority'],exact_name),exact_name,
                            profile={'authority':race['authority'],'source_namespace':'RECOVERED_JAN_RAW',
                                     'identity_resolution':'EXACT_SOURCE_NAME_BUCKET_NOT_CANONICAL',
                                     'canonical_identity_verified':False,'same_name_ambiguity':'UNRESOLVED'})
                        jockey_ids.add(jockey_id)
                    observation=candidate['observations'] if candidate else {}
                    result=results.get(horse['number'])
                    details={'reconstructed_pre':{'stage':'PRE_RECONSTRUCTION','temporal_class':'UNKNOWN_TIMESTAMP','available_at':None,
                              'values':{'age':horse.get('age'),'normalized_carried_weight_kg':horse.get('weight'),
                                        'recovered_carried_weight_kg':observation.get('carried_weight_kg'),
                                        'career_aggregates_unverified':horse.get('career',{})},
                              'quarantine_candidate_hash':candidate['candidate_hash'] if candidate else None},
                             'post_result':{'stage':'POST','available_at':None,'rank':result.get('rank') if result else None,
                                            'status':result.get('status') if result else None,
                                            'recorded_win_payout_per_100_yen':race.get('win_payouts',{}).get(str(horse['number'])),
                                            'raw_post_source_details':raw_row.get('post_source_details',{}) if raw_row else {},
                                            'missing_payout_is_not_synthetic_zero':True},
                             'source_ref':source_ref,'source_row_identity_quality':horse.get('identity_quality','UNKNOWN')}
                    frame=observation.get('frame_no') if candidate else horse.get('frame')
                    entry_ids.add(store.add_entry(race['race_id'],horse['number'],horse_id,jockey_id=jockey_id,frame_no=frame,details=details))
                    counts['january_entries' if race['date'].startswith('202601') else 'december_entries']+=1
                    if candidate is not None:
                        observation_ids.add(store.add_observation(horse_id,race['race_id'],candidate,
                            source_ref=candidate['source']['source_ref'],available_at=None,temporal_class='UNKNOWN_TIMESTAMP'))
                        extra=raw_row.get('extra_source_details',{})
                        if extra:
                            payload={'schema':'prism.recovered-source-details/v1','stage':'PRE_RECONSTRUCTION',
                                     'phase':'UNKNOWN','mode':'HISTORICAL_RECONSTRUCTION',
                                     'temporal_class':'UNKNOWN_TIMESTAMP','available_at':None,
                                     'race_id':race['race_id'],'horse_no':horse['number'],
                                     'extra_source_details':extra,'as_of_verified':False,'engine_ready':False,
                                     'source_record_hash':candidate['source']['source_record_hash'],
                                     'note':'Raw values only; aggregate career and best-time fields may be final snapshots, not certified PRE features.'}
                            detail_observation_ids.add(store.add_observation(horse_id,race['race_id'],payload,
                                source_ref=candidate['source']['source_ref']+':EXTRA_DETAILS',available_at=None,temporal_class='UNKNOWN_TIMESTAMP'))
                            counts['nar_detail_observations' if race['authority']=='NAR' else 'jra_detail_observations']+=1
            summary={'schema':'prism.entity-import-receipt/v1','status':'RECOVERED_RECORDS_IMPORTED_NOT_CANONICAL_OR_PRE_CERTIFIED',
                     'source_hashes':source_hashes,'source_bundle_hash':source_hash,
                     'importer_code_hash':sha256(Path(__file__).read_bytes()).hexdigest(),
                     'counts':{'races':len(race_ids),'horses_provisional':len(horse_ids),'jockey_name_buckets_provisional':len(jockey_ids),
                               'entries':len(entry_ids),'december_entries':counts['december_entries'],'january_entries':counts['january_entries'],
                               'quarantined_observations':len(observation_ids),'imported_discussion_evaluations':0,
                               'extra_source_detail_observations':len(detail_observation_ids),
                               'nar_detail_observations':counts['nar_detail_observations'],
                               'jra_detail_observations':counts['jra_detail_observations'],
                               'canonical_horse_ids_verified':0,'canonical_jockey_ids_verified':0,'pre_certified_observations':0},
                     'post_result_separated_from_reconstructed_pre':True,'name_only_horse_merge_allowed':False,
                     'same_name_jockey_identity_verified':False,'mock_discussion_evaluations_created':False,
                     'individual_records_published':False,'trained_model_complete':False,
                     'idempotence':'Same receipt/source hash returns original receipt without modifying entity records; changed source is rejected.',
                     'limitations':['Horse IDs are source-scoped provisional composites, not official lifetime IDs.',
                                    'Jockey exact-name buckets remain authority-scoped and same-name ambiguity is unresolved.',
                                    'Historical observations have unknown publication time; POST ranks/payouts are stored separately.',
                                    'December jockey links and detailed raw observations were not imported; January raw only.',
                                    'No synthetic discussion evaluations or model-training achievement is created.']}
            summary['receipt_hash']=digest(summary)
            store.connection.execute('INSERT INTO _prism_entity_imports VALUES (?,?,?)',
                                     (RECEIPT_KEY,source_hash,json.dumps(summary,ensure_ascii=False,sort_keys=True,separators=(',',':'))))
        if [row[0] for row in store.connection.execute('PRAGMA quick_check')]!=['ok']:raise ValueError('post-commit database integrity check failed')
        if store.connection.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('post-commit database foreign key check failed')
        return summary
    finally:store.close()


def run(january_path,bootstrap_path,raw_root,hold_root,db_path):
    bootstrap,january,raw,held,hashes=load_inputs(january_path,bootstrap_path,raw_root,hold_root)
    return import_rows(db_path,bootstrap,january,raw,held,hashes)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--january',required=True);parser.add_argument('--bootstrap',required=True)
    parser.add_argument('--raw-root',required=True);parser.add_argument('--hold-root',required=True)
    parser.add_argument('--db',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
    summary=run(args.january,args.bootstrap,args.raw_root,args.hold_root,args.db)
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':summary['status'],'counts':summary['counts'],'receipt_hash':summary['receipt_hash']},ensure_ascii=False))
