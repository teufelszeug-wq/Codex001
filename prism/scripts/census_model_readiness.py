"""Aggregate-only feature census; result-bearing archives are not PRE inputs.

This measures data already recovered, not model quality or new feature estimates.
Historical ordinal scores are counted only after a race's advertised-start batch.
Their historical publication timestamps remain uncertified.
"""
import argparse
from collections import Counter,defaultdict
import csv
from hashlib import sha256
import io
from itertools import groupby
import json
from math import isfinite
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile


def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def valid_number(value,low=None,high=None):
    return (type(value) in (int,float) and isfinite(value)
            and (low is None or value>=low) and (high is None or value<=high))


def nonempty(value):
    return isinstance(value,str) and bool(value.strip())


def career_available(horse,key):
    value=horse.get('career',{}).get(key)
    return isinstance(value,list) and len(value)==4 and all(type(n) is int and n>=0 for n in value)


def history_updates(race):
    started=[r for r in race.get('results',[]) if r.get('status') not in ('取消','除外','取止','競走除外')]
    n=len(started)
    if n<2:return []
    ranks={r['number']:r.get('rank') for r in started if type(r.get('rank')) is int and 1<=r['rank']<=n}
    complete_course=(nonempty(race.get('venue')) and race.get('surface') in {'TURF','DIRT','BANEI','JUMP'}
                     and valid_number(race.get('distance'),100,10000)
                     and race.get('direction') in {'LEFT','RIGHT','STRAIGHT','MIXED'})
    return [(h['identity'],{'date':race['date'],'surface':race['surface'],'complete_course':complete_course})
            for h in race['entrants'] if nonempty(h.get('identity')) and h['number'] in ranks]


RUNNER_FIELDS={
    'horse_number':(lambda h:type(h.get('number')) is int and h['number']>0,'Map number; verify official entrant list rather than result-table membership.'),
    'frame_number':(lambda h:type(h.get('frame')) is int and 1<=h['frame']<=8,'Map frame only when present; never infer it from horse number.'),
    'barrier_position':(lambda h:type(h.get('barrier_no')) is int,'Explicit barrier position and original field width are missing; do not silently substitute horse/frame number.'),
    'horse_identity_nonempty':(lambda h:nonempty(h.get('identity')),'Composite identities need canonical horse-ID resolution and ambiguity checks.'),
    'carried_weight':(lambda h:valid_number(h.get('weight'),1,2000),'Map parser weight (burden/carried weight), never body weight.'),
    'career_all_aggregate':(lambda h:career_available(h,'全成績'),'Four count values exist for some NAR runners; no dated per-race history or PRE availability proof.'),
    'career_venue_aggregate':(lambda h:career_available(h,'当競馬場成績'),'Aggregate venue counts are not normalized CAI scores.'),
    'career_distance_aggregate':(lambda h:career_available(h,'うち当距離成績'),'Aggregate distance counts are not normalized DAI scores.'),
    'state_readiness':(lambda h:isinstance(h.get('state'),dict) and valid_number(h['state'].get('readiness'),0,100),'Acquire pre-race state observations; do not zero-fill readiness.'),
    'pace_style_complete':(lambda h:isinstance(h.get('style'),dict) and all(valid_number(h['style'].get(k)) for k in ('escape','front','mid','closer','early_speed','resistance')),'Acquire pre-race style/sectional observations and validate style normalization.'),
    'workout_observations':(lambda h:isinstance(h.get('workout'),dict) and bool(h['workout']),'Acquire dated workout distance/time/reference measurements; adapter code alone is not data.'),
    'body_condition_observations':(lambda h:isinstance(h.get('condition'),dict) and bool(h['condition']),'Acquire body weight/change and condition assessment; carried weight is not body weight.'),
    'jockey_observations':(lambda h:isinstance(h.get('jockey'),dict) and bool(h['jockey']),'Acquire jockey identity and prior wins/rides with a PRE cut-off.'),
    'sectional_observations':(lambda h:isinstance(h.get('sectional'),dict) and bool(h['sectional']),'Acquire individual sectional times/position; unsupported routes remain unavailable.'),
    'path_position':(lambda h:valid_number(h.get('path_position'),-1,1),'Acquire pre-race projected path; do not use the observed result-day path as PRE.'),
    'banei_special_observations':(lambda h:isinstance(h.get('ban_ei'),dict) and bool(h['ban_ei']),'Acquire barrier skill/pulling power; moisture is a separate race observation.'),
    'jump_special_observations':(lambda h:isinstance(h.get('jump'),dict) and bool(h['jump']),'Acquire jump skill/evidence rather than reusing flat coefficients.'),
}
RACE_FIELDS={
    'race_surface':(lambda r:r.get('surface') in {'TURF','DIRT','BANEI','JUMP'},'Map surface; audit parser category routing.'),
    'race_distance':(lambda r:valid_number(r.get('distance'),100,10000),'Map distance to distance_m.'),
    'race_direction':(lambda r:r.get('direction') in {'LEFT','RIGHT','STRAIGHT','MIXED'},'Map direction; MIXED requires venue/course resolution.'),
    'race_venue':(lambda r:nonempty(r.get('venue')),'Normalize venue identity, not just display text.'),
    'class_normalized_rating':(lambda r:valid_number(r.get('class_rating'),0,100),'Race title exists but is not a validated numeric class/speed rating.'),
    'bias_tbi_ssi_observations':(lambda r:isinstance(r.get('bias'),dict) and all(valid_number(r['bias'].get(k)) for k in ('gate','path','front','ssi')),'Acquire timestamped signed lane/front bias and SSI observations.'),
    'specialist_evidence_signals':(lambda r:isinstance(r.get('specialists'),list) and bool(r['specialists']),'No trained specialist signals/evidence found; names and role-play are not models.'),
    'market_quotes':(lambda r:isinstance(r.get('market'),dict) and bool(r['market'].get('quotes')),'Acquire timestamped pre-result quotes after prediction lock; do not use final payout as odds.'),
    'calibration_artifact':(lambda r:isinstance(r.get('calibration'),dict) and bool(r['calibration']),'Fit on disjoint earlier outcomes with availability times; no calibrated full engine artifact recovered.'),
    'result_rank_labels_post_only':(lambda r:bool(r.get('results')) and any(type(x.get('rank')) is int for x in r['results']),'Evaluator only; reveal after locking predictions, never current-race PRE features.'),
    'win_payout_labels_post_only':(lambda r:isinstance(r.get('win_payouts'),dict) and bool(r['win_payouts']),'Evaluator-only official payout, not a market quote or input feature.'),
}


def row(count,denominator,gap,scope='RUNNER'):
    return {'available_count':count,'denominator':denominator,'missing_count':denominator-count,
            'missing_rate':(denominator-count)/denominator if denominator else None,
            'scope':scope,'historical_timestamp_certified_count':0,
            'historical_timestamp_certification':'UNKNOWN_TIMESTAMP_NOT_PRE_CERTIFIED',
            'adapter_gap':gap}


def census(rows,bootstrap=()):
    if len({r['race_id'] for r in rows})!=len(rows):raise ValueError('duplicate race identity')
    if bootstrap and rows and any(r['date']>=min(x['date'] for x in rows) for r in bootstrap):raise ValueError('bootstrap chronology rejected')
    runners=[h for r in rows for h in r['entrants']];denominator=len(runners)
    values={}
    for key,(test,gap) in RUNNER_FIELDS.items():
        surfaces=({'BANEI'} if key=='banei_special_observations' else {'JUMP'} if key=='jump_special_observations'
                  else {'TURF','DIRT'} if key in {'pace_style_complete','sectional_observations'} else None)
        eligible=[h for r in rows for h in r['entrants'] if surfaces is None or r.get('surface') in surfaces]
        values[key]=row(sum(bool(test(h)) for h in eligible),len(eligible),gap)
        if surfaces is not None:values[key]['applicable_surfaces']=sorted(surfaces)
    values.update({k:row(sum(bool(test(r)) for r in rows),len(rows),gap,'RACE') for k,(test,gap) in RACE_FIELDS.items()})
    history=defaultdict(list);counts=Counter()
    for race in sorted(bootstrap,key=lambda r:(r['date'],r['start'],r['race_id'])):
        for identity,record in history_updates(race):history[identity].append(record)
    for _,batch in groupby(sorted(rows,key=lambda r:(r['date'],r['start'],r['race_id'])),lambda r:(r['date'],r['start'])):
        batch=list(batch)
        for race in batch:
            for horse in race['entrants']:
                prior=history.get(horse.get('identity'),[])
                same=[h for h in prior if h['surface']==race['surface']]
                counts['base_ability_ordinal_proxy']+=bool(same)
                counts['base_ability_prior_day_proxy']+=any(h['date']<race['date'] for h in same)
                counts['course_history_descriptors']+=any(h['complete_course'] for h in same)
                counts['rotation_days_derived']+=bool(prior)
                counts['nvalue_recent_peak_reconstruction']+=bool(same)
        # Same advertised start: all predictions would lock before any updates.
        for race in batch:
            for identity,record in history_updates(race):history[identity].append(record)
    derived_gaps={
        'base_ability_ordinal_proxy':'Existing Jan ability-only B0 baseline used reconstructed rank percentile and recency, not normalized speed/class. Same-start-batch embargo only; availability is unproved.',
        'base_ability_prior_day_proxy':'Conservative prior-day history availability proxy; next-day rule is not proof of historical publication time.',
        'course_history_descriptors':'Dated reconstructed surface/distance/direction/venue descriptors exist; numeric class and performance normalization remain absent.',
        'rotation_days_derived':'Days since a prior recovered race are derivable; state readiness is absent and full lifetime race history is incomplete.',
        'nvalue_recent_peak_reconstruction':'A recent rank-proxy peak is derivable; no independent trained NValue model or post-lock market edge has been validated.',
    }
    values.update({k:row(counts[k],denominator,gap,'DERIVED_RUNNER_RECONSTRUCTION') for k,gap in derived_gaps.items()})
    return {'races':len(rows),'runners':denominator,'authorities':dict(sorted(Counter(r.get('authority','UNKNOWN') for r in rows).items())),
            'surfaces':dict(sorted(Counter(r.get('surface','UNKNOWN') for r in rows).items())),
            'identity_quality':dict(sorted(Counter(h.get('identity_quality','UNKNOWN') for h in runners).items())),
            'canonical_dataset_hash':digest([{k:v for k,v in r.items() if k!='source'} for r in rows]),
            'features':values}


def inventory_evidence(roots):
    filenames=[]
    for root in roots:
        result=subprocess.run(['rg','--files',str(root)],text=True,capture_output=True,check=False)
        if result.returncode not in (0,1):raise ValueError('file inventory failed')
        filenames.extend(result.stdout.splitlines())
    filenames=sorted(set(filenames))
    candidates=[name for name in filenames if re.search(r'(?:2026[-_]?02|february|replay_feb|2月)',name,re.IGNORECASE)]
    return {'method':'rg --files; filename February-token scan, not whole-content proof',
            'scanned_root_count':len(roots),'scanned_file_count':len(filenames),'inventory_hash':digest(filenames),
            'february_filename_candidates':len(candidates),'february_filename_candidates_hash':digest(candidates),
            'february_recovery_status':'CANDIDATES_REQUIRE_DATASET_VALIDATION' if candidates else 'NOT_RECOVERED_IN_SCANNED_FILES',
            'complete_february_coverage_verified':False}


def raw_archive_census(root):
    """Count recoverable raw values without copying names or result rows out."""
    from lxml import html
    root=Path(root);counts=Counter();denominators=Counter();source_hashes=[]
    def numeric_text(value):return bool(re.search(r'\d',value or ''))
    def observe(authority,values):
        denominators[authority]+=1
        for key,present in values.items():counts[(authority,key)]+=bool(present)
    archive=root/'nar_202601_official.zip'
    if archive.exists():
        source_hashes.append(sha256(archive.read_bytes()).hexdigest())
        with ZipFile(archive) as zipped:
            name=next(n for n in zipped.namelist() if n.endswith('_horselist.csv'))
            for record in csv.DictReader(io.StringIO(zipped.read(name).decode('utf-8-sig'))):
                if not record.get('競走年月日','').startswith('202601'):continue
                observe('NAR',{
                    'frame_recoverable':numeric_text(record.get('枠番')),
                    'carried_weight_recoverable':numeric_text(record.get('負担重量')),
                    'body_weight_observation':numeric_text(record.get('馬体重')),
                    'body_weight_change_observation':numeric_text(record.get('馬体重増減')),
                    'jockey_identity':nonempty(record.get('騎手名')),
                    'jockey_career_aggregate':len(re.findall(r'\d+',record.get('騎手成績','')))==4,
                    'current_race_sectional_post_only':numeric_text(record.get('上がり3F')),
                    'current_race_corner_positions_post_only':False,
                })
    pages=sorted(p for p in (root/'jra_racingviewer').glob('202601*/*.htm'))
    for page in pages:
        content=page.read_bytes();source_hashes.append(sha256(content).hexdigest());tree=html.fromstring(content)
        for tr in tree.xpath('//table[contains(@class,"striped")]//tr[td]'):
            cells={td.get('class'):td for td in tr.xpath('./td')}
            text=lambda key:''.join(cells[key].itertext()).strip() if key in cells else ''
            if not numeric_text(text('num')):continue
            frame=text('waku')
            if 'waku' in cells:frame+=' '.join(cells['waku'].xpath('.//img/@alt'))
            observe('JRA',{
                'frame_recoverable':numeric_text(frame),
                'carried_weight_recoverable':numeric_text(text('weight')),
                'body_weight_observation':numeric_text(text('h_weight')),
                'body_weight_change_observation':bool(re.search(r'\([+\-]?\d+\)',text('h_weight'))),
                'jockey_identity':nonempty(text('jockey')),
                'jockey_career_aggregate':False,
                'current_race_sectional_post_only':numeric_text(text('f_time')),
                'current_race_corner_positions_post_only':numeric_text(text('corner')),
            })
    gap={
        'frame_recoverable':'JRA frame is encoded in image alt text; normalized parser currently reads text only. Frame is not barrier position.',
        'carried_weight_recoverable':'Strip apprentice/claim markers safely before numeric parsing; do not read this as body weight.',
        'body_weight_observation':'Raw values exist but normalized dataset drops them. Extract weight/change separately; acquire historical publication time and condition assessment.',
        'body_weight_change_observation':'Raw values exist but normalized dataset drops them. Do not fabricate a condition score or PRE timestamp.',
        'jockey_identity':'Raw rider names exist but normalized dataset drops them; canonical ID resolution and prior race aggregation are still required.',
        'jockey_career_aggregate':'NAR raw aggregate may be recoverable; parse/validate four counts and establish as-of time before adaptation.',
        'current_race_sectional_post_only':'Current-race realized sectional is POST-only. It may enter future history only after result availability, never this race PRE.',
        'current_race_corner_positions_post_only':'Current-race realized positions are POST-only; not pre-race style or projected path.',
    }
    return {'status':'RAW_VALUE_RECOVERABILITY_NOT_PRE_OR_MODEL_ACCEPTANCE','source_files':len(source_hashes),
            'source_content_collection_hash':digest(sorted(source_hashes)),
            'authorities':{authority:{'runners':total,'features':{
                key:row(counts[(authority,key)],total,message,'RAW_RUNNER_VALUE') for key,message in gap.items()}}
                for authority,total in sorted(denominators.items())},
            'publication_timestamps_certified':False,
            'note':'Only actual nonempty raw values are counted. Dropped parser fields are distinct from data absent from all recovered sources.'}


def extract_hold_store(root,january,out):
    """Private intermediate store; only the aggregate return belongs in Git."""
    from lxml import html
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
    from prism_engine.recovered_observations import extract_nar_candidate,extract_jra_candidate
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    nar_races={(r['date'],r['venue'],r['number']):r for r in january if r['authority']=='NAR'}
    jra_races={str(r['source']).split('jra_racingviewer/')[-1]:r for r in january if r['authority']=='JRA'}
    seen=set();hashes=[];coverage=Counter();total=Counter()
    expected={(r['race_id'],h['number']) for r in january for h in r['entrants']}
    def save(record):
        key=(record['race_id'],record['horse_identity']['horse_no'])
        if key in seen or key not in expected:raise ValueError('quarantine duplicate or unexpected entrant')
        seen.add(key);hashes.append(record['candidate_hash']);total['candidates']+=1
        for name,value in record['observations'].items():coverage[name]+=value is not None
        (out/(digest(key)+'.json')).write_text(json.dumps(record,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    with ZipFile(root/'nar_202601_official.zip') as zipped:
        name=next(n for n in zipped.namelist() if n.endswith('_horselist.csv'))
        for record in csv.DictReader(io.StringIO(zipped.read(name).decode('utf-8-sig'))):
            key=(record.get('競走年月日'),record.get('競馬場'),int(record['レース番号']))
            if key not in nar_races:continue
            save(extract_nar_candidate(record,nar_races[key]['race_id'],'RECOVERED_NAR_OFFICIAL_MONTHLY_202601'))
    for key,race in sorted(jra_races.items()):
        tree=html.fromstring((root/'jra_racingviewer'/key).read_bytes())
        for tr in tree.xpath('//table[contains(@class,"striped")]//tr[td]'):
            elements={td.get('class'):td for td in tr.xpath('./td')}
            cells={name:''.join(td.itertext()).strip() for name,td in elements.items()}
            if not re.search(r'\d',cells.get('num','')):continue
            alt=' '.join(elements['waku'].xpath('.//img/@alt')) if 'waku' in elements else ''
            save(extract_jra_candidate(cells,race['race_id'],'RECOVERED_JRA_RACING_VIEWER_202601',frame_image_alt=alt))
    if seen!=expected:raise ValueError('quarantine coverage mismatch')
    return {'status':'EXTRACTED_TO_PRIVATE_QUARANTINE_NOT_ENGINE_INPUT','candidate_count':total['candidates'],
            'expected_runner_count':len(expected),'coverage_complete':True,
            'candidate_collection_hash':digest(sorted(hashes)),'available_observation_counts':dict(sorted(coverage.items())),
            'unknown_availability_count':total['candidates'],'unresolved_canonical_horse_id_count':total['candidates'],
            'engine_ready_count':0,'pre_certified_count':0,'trained_model_count':0,
            'public_artifact_contains_individual_records':False}


def build_report(january,bootstrap,inventory,raw_census=None,hold_extraction=None):
    if any(not r.get('date','').startswith('202601') for r in january):raise ValueError('January universe required')
    if any(not r.get('date','').startswith('202512') for r in bootstrap):raise ValueError('December bootstrap required')
    report={'schema':'prism.model-readiness-census/v1','status':'DATA_GAP_CENSUS_NOT_FULL_MODEL_ACCEPTANCE',
            'historical_mode':'HISTORICAL_RECONSTRUCTION','strict_pre_certified_races':0,
            'january':census(january,bootstrap),'december_bootstrap':census(bootstrap),'file_inventory':inventory,
            'raw_archive_census':raw_census,
            'hold_store_extraction':hold_extraction,
            'baseline_status':'January ability-only B0 was already executed; this census does not rerun it or establish new model performance.',
            'limitations':['Aggregate counts only; no horse names, race records or raw archive content are published.',
                           'Recovered result-bearing objects are evaluator sources, never direct engine PRE inputs.',
                           'Available values do not establish historical publication, canonical identity or predictive utility.',
                           'Absent modules are not zero-imputed or included in a pretend full-model comparison.',
                           'NAR career aggregates may encode result-day/final snapshots; unavailable timing prevents PRE certification.',
                           'Normalized field absence does not mean raw-source absence: raw_archive_census distinguishes recoverable values dropped by adapters.',
                           'Explicit barrier width/position, numeric class normalization and timestamps still block strict raw engine adaptation.'],
            'phase_b_empirical_model_complete':False,'performance_validated':False}
    report['report_hash']=digest(report)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--january',required=True);parser.add_argument('--bootstrap',required=True)
    parser.add_argument('--scan-root',action='append',required=True);parser.add_argument('--raw-root');parser.add_argument('--hold-store-out')
    parser.add_argument('--out',required=True);args=parser.parse_args()
    january=json.loads(Path(args.january).read_text());bootstrap=json.loads(Path(args.bootstrap).read_text())
    if args.hold_store_out and not args.raw_root:parser.error('--hold-store-out requires --raw-root')
    inventory=inventory_evidence(args.scan_root)
    report=build_report(january,bootstrap,inventory,raw_archive_census(args.raw_root) if args.raw_root else None,
                        extract_hold_store(args.raw_root,january,args.hold_store_out) if args.hold_store_out else None)
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'january_races':report['january']['races'],'january_runners':report['january']['runners'],
                      'report_hash':report['report_hash'],'strict_pre_certified_races':0},ensure_ascii=False))
