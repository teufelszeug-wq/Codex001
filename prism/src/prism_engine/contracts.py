"""Canonical input boundaries. Hashes establish integrity, not external truth."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite

MODES={'SYNTHETIC','HISTORICAL_RECONSTRUCTION','PRE_AVAILABLE'}
SURFACES={'TURF','DIRT','JUMP','BANEI'}

def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def timestamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)

def numeric(value,low=None,high=None):
    if type(value) not in (int,float) or not isfinite(value):raise ValueError('finite numeric value required')
    if low is not None and value<low or high is not None and value>high:raise ValueError('numeric range violation')
    return float(value)

def fields(value,allowed,required=()):
    if not isinstance(value,dict) or set(value)-set(allowed) or set(required)-set(value):raise ValueError('input contract fields rejected')

def validate(raw):
    fields(raw,{'schema','mode','race','runners','bias','specialists','source'}, {'schema','mode','race','runners','source'})
    if raw['schema'] not in {'prism.engine.raw/v1','prism.engine.raw/v2'} or raw['mode'] not in MODES:raise ValueError('schema or mode rejected')
    v2=raw['schema']=='prism.engine.raw/v2'
    race_fields={'race_id','venue','surface','distance_m','direction','class_rating','cutoff','barrier_count'}
    if v2:race_fields.add('declaration_stage')
    fields(raw['race'],race_fields,race_fields)
    race=raw['race'];cutoff=timestamp(race['cutoff'])
    stage=race.get('declaration_stage','DRAW_CONFIRMED')
    if stage not in {'ENTRIES_CONFIRMED','DRAW_CONFIRMED'}:raise ValueError('declaration stage rejected')
    if not isinstance(race['race_id'],str) or not race['race_id']:raise ValueError('race identity required')
    if race['surface'] not in SURFACES or race['direction'] not in {'LEFT','RIGHT','STRAIGHT','MIXED'}:raise ValueError('course category rejected')
    numeric(race['distance_m'],100,10000);numeric(race['class_rating'],0,100)
    if type(race['barrier_count']) is not int or not 2<=race['barrier_count']<=24:raise ValueError('explicit barrier width required')
    source_fields={'source_id','available_at','content_hash'}
    if v2:source_fields.add('racecard_sha256')
    fields(raw['source'],source_fields,{'source_id','available_at','content_hash'})
    source=raw['source']
    if not source['source_id']:raise ValueError('source ID required')
    if source['available_at'] is None:
        if raw['mode']!='HISTORICAL_RECONSTRUCTION':raise ValueError('unknown source time')
    elif timestamp(source['available_at'])>cutoff:raise ValueError('future source')
    payload={k:v for k,v in raw.items() if k!='source'}
    if source['content_hash']!=digest(payload):raise ValueError('source hash mismatch')
    if not isinstance(raw['runners'],list) or not 2<=len(raw['runners'])<=24:raise ValueError('2..24 runners required')
    seen=set();ids=set();barriers=set()
    for runner in raw['runners']:
        allowed={'horse_id','horse_no','frame_no','barrier_no','carried_weight','history','state','style','workout','condition','jockey','sectional','ban_ei','jump','path_position'}
        if v2:allowed.add('provenance')
        fields(runner,allowed,{'horse_id','horse_no','frame_no','barrier_no','carried_weight','history'})
        if not isinstance(runner['horse_id'],str) or not runner['horse_id'] or runner['horse_id'] in ids:raise ValueError('horse identity ambiguous')
        number=runner['horse_no'];frame=runner['frame_no'];barrier=runner['barrier_no']
        undrawn=v2 and stage=='ENTRIES_CONFIRMED'
        if not (undrawn and number is None):
            if type(number) is not int or number<1 or number in seen:raise ValueError('horse number duplicate/invalid')
            seen.add(number)
        if not (undrawn and frame is None) and (type(frame) is not int or not 1<=frame<=8):raise ValueError('frame number invalid')
        numeric(runner['carried_weight'],1,2000);ids.add(runner['horse_id'])
        if not (undrawn and barrier is None):
            if type(barrier) is not int or not 1<=barrier<=race['barrier_count'] or barrier in barriers:raise ValueError('invalid barrier position')
            barriers.add(barrier)
        provenance=runner.get('provenance')
        if provenance is not None:
            fields(provenance,{'source_url','available_at','content_hash'},{'source_url','available_at','content_hash'})
            if not isinstance(provenance['source_url'],str) or not provenance['source_url'].startswith('https://'):raise ValueError('runner evidence source required')
            if not isinstance(provenance['content_hash'],str) or len(provenance['content_hash'])!=64 or any(c not in '0123456789abcdef' for c in provenance['content_hash']):raise ValueError('runner evidence hash required')
            if timestamp(provenance['available_at'])>cutoff:raise ValueError('future runner evidence')
        if runner.get('path_position') is not None:numeric(runner['path_position'],-1,1)
        if not isinstance(runner['history'],list):raise ValueError('history list required')
        for h in runner['history']:
            fields(h,{'occurred_at','available_at','performance_score','distance_m','surface','direction','class_rating','venue'},
                   {'occurred_at','available_at','performance_score','distance_m','surface','direction','class_rating','venue'})
            occurred=timestamp(h['occurred_at'])
            if occurred>=cutoff:raise ValueError('same/future race history')
            if h['available_at'] is None:
                if raw['mode']!='HISTORICAL_RECONSTRUCTION':raise ValueError('unknown history time')
            elif not occurred<=timestamp(h['available_at'])<=cutoff:raise ValueError('history availability rejected')
            numeric(h['performance_score'],0,100);numeric(h['distance_m'],100,10000);numeric(h['class_rating'],0,100)
            if h['surface'] not in SURFACES or h['direction'] not in {'LEFT','RIGHT','STRAIGHT','MIXED'}:raise ValueError('history course rejected')
        bounded={'state':{'readiness':(0,100),'rotation_days':(0,3650)},
                 'style':{'escape':(0,1),'front':(0,1),'mid':(0,1),'closer':(0,1),'early_speed':(0,100),'resistance':(0,100)},
                 'workout':{'score':(0,100)},'condition':{'score':(0,100)},'jockey':{'score':(0,100),'sample_size':(0,100000)},
                 'sectional':{'score':(0,100)},'ban_ei':{'barrier_skill':(0,100),'pulling_power':(0,100)},'jump':{'jump_skill':(0,100)}}
        for name,ranges in bounded.items():
            item=runner.get(name)
            if item is None:continue
            fields(item,set(ranges)|{'available_at'},set(ranges)|{'available_at'})
            if item['available_at'] is None:
                if raw['mode']!='HISTORICAL_RECONSTRUCTION':raise ValueError('unknown feature time')
            elif timestamp(item['available_at'])>cutoff:raise ValueError('future feature')
            for key,(lo,hi) in ranges.items():numeric(item[key],lo,hi)
            if name=='style' and sum(item[k] for k in ('escape','front','mid','closer'))<=0:raise ValueError('empty style')
    bias=raw.get('bias')
    if bias is not None:
        fields(bias,{'gate','path','front','ssi','water_content','positive_lane','available_at'},
               {'gate','path','front','ssi','positive_lane','available_at'})
        if bias['positive_lane'] not in {'OUTER','INNER'}:raise ValueError('bias sign convention required')
        for k in ('gate','path','front','ssi'):numeric(bias[k],-1,1)
        if 'water_content' in bias:numeric(bias['water_content'],0,100)
        if bias['available_at'] is None:
            if raw['mode']!='HISTORICAL_RECONSTRUCTION':raise ValueError('unknown bias time')
        elif timestamp(bias['available_at'])>cutoff:raise ValueError('future bias')
    refs=set()
    for s in raw.get('specialists',[]):
        fields(s,{'horse_id','agent_id','evidence_id','delta','confidence','available_at'},
               {'horse_id','agent_id','evidence_id','delta','confidence','available_at'})
        if s['horse_id'] not in ids or not s['agent_id'] or not s['evidence_id']:raise ValueError('invalid specialist identity')
        key=(s['horse_id'],s['agent_id'],s['evidence_id'])
        if key in refs:raise ValueError('duplicate specialist signal')
        refs.add(key);numeric(s['delta'],-10,10);numeric(s['confidence'],0,1)
        if timestamp(s['available_at'])>cutoff:raise ValueError('future specialist')
    return deepcopy(raw)
