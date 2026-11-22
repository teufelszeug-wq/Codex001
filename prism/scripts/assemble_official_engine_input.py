"""Join official racecard to timestamped horse evidence without inventing features.

Requires source-backed historical observations per horse; a racecard alone is not
a calibrated prediction input. This adapter deliberately refuses empty evidence.
"""
from copy import deepcopy
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from prism_engine.contracts import digest,validate,timestamp

def assemble_engine_input(card, evidence, *, venue, surface, distance_m,
                          direction, class_rating, barrier_count, locked_at):
    if card.get('schema') not in {'prism.official_racecard/v1','prism.official_racecard/v2'}:
        raise ValueError('normalized official racecard required')
    synthetic=card.get('mode')=='SYNTHETIC'
    if card.get('source_verified') is not True and not synthetic:
        raise ValueError('official racecard identity has not been verified')
    if not isinstance(evidence,dict):
        raise ValueError('horse evidence mapping required')
    locked=timestamp(locked_at)
    if locked>=timestamp(card['off_at']):
        raise ValueError('prediction not before off')
    if timestamp(card['captured_at'])>locked:
        raise ValueError('racecard not available at prediction time')
    active=card['active_runners']
    v2=card['schema']=='prism.official_racecard/v2'
    stage=card.get('declaration_stage','DRAW_CONFIRMED')
    if stage not in {'ENTRIES_CONFIRMED','DRAW_CONFIRMED'}:
        raise ValueError('declaration stage rejected')
    if v2 and any(not isinstance(r.get('horse_id'),str) or not r['horse_id'] for r in active):
        raise ValueError('official horse identity required before evidence join')
    ids={r['horse_id'] if v2 else str(r['horse_no']) for r in active}
    if len(ids)!=len(active):
        raise ValueError('duplicate official horse identity')
    if set(evidence)!=ids:
        raise ValueError('complete evidence required for all active horses')
    runners=[];names={}
    for horse in active:
        key=horse['horse_id'] if v2 else str(horse['horse_no'])
        entry=deepcopy(evidence[key])
        if not isinstance(entry,dict) or not entry.get('horse_id') or not entry.get('history'):
            raise ValueError('real horse identity and prior history required')
        if not isinstance(entry['history'],list):
            raise ValueError('history must be list')
        if not entry.get('source_url') or not entry.get('available_at'):
            raise ValueError('horse evidence provenance required')
        if timestamp(entry['available_at'])>locked:
            raise ValueError('horse evidence from future')
        provenance={'source_url':entry['source_url'],'available_at':entry['available_at'],
                    'content_hash':digest(entry)}
        horse_id=entry.pop('horse_id')
        if v2 and horse_id!=horse['horse_id']:
            raise ValueError('horse evidence identity mismatch')
        entry.pop('source_url');entry.pop('available_at')
        if horse_id in names:
            raise ValueError('duplicate horse identity')
        names[horse_id]=horse['horse_name']
        if set(entry)&{'horse_no','frame_no','barrier_no','provenance'}:
            raise ValueError('evidence cannot override official draw or provenance')
        # A scratch never renumbers the surviving starting stalls. Before the
        # draw there is no barrier position to infer from the order of entries.
        barrier=horse.get('barrier_no',horse.get('horse_no')) if stage=='DRAW_CONFIRMED' else None
        runners.append({'horse_id':horse_id,'horse_no':horse.get('horse_no'),
                        'frame_no':horse.get('frame_no'),'barrier_no':barrier,
                        'carried_weight':entry.pop('carried_weight'),
                        'history':entry.pop('history'),'provenance':provenance,**entry})
    raw={'schema':'prism.engine.raw/v2','mode':'SYNTHETIC' if synthetic else 'PRE_AVAILABLE',
         'race':{'race_id':card['race_id'],'venue':venue,'surface':surface,
                 'distance_m':distance_m,'direction':direction,
                 'class_rating':class_rating,'cutoff':card['off_at'],
                 'barrier_count':barrier_count,'declaration_stage':stage},
         'runners':runners,
         'source':{'source_id':card['official_url'],'available_at':card['captured_at'],
                   'racecard_sha256':digest(card),'content_hash':''}}
    raw['source']['content_hash']=digest({k:v for k,v in raw.items() if k!='source'})
    validate(raw)
    return raw,names
