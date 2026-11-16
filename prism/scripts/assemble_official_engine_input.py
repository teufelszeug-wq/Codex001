"""Join official racecard to timestamped horse evidence without inventing features.

Requires source-backed historical observations per horse; a racecard alone is not
a calibrated prediction input. This adapter deliberately refuses empty evidence.
"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from prism_engine.contracts import digest,validate,timestamp

def assemble_engine_input(card, evidence, *, venue, surface, distance_m,
                          direction, class_rating, barrier_count, locked_at):
    if card.get('schema')!='prism.official_racecard/v1':
        raise ValueError('normalized official racecard required')
    if card.get('source_verified') is not True:
        raise ValueError('official racecard identity has not been verified')
    if not isinstance(evidence,dict):
        raise ValueError('horse evidence mapping required')
    locked=timestamp(locked_at)
    if locked>=timestamp(card['off_at']):
        raise ValueError('prediction not before off')
    if timestamp(card['captured_at'])>locked:
        raise ValueError('racecard not available at prediction time')
    active=card['active_runners']
    ids={str(r['horse_no']) for r in active}
    # A set comparison alone silently collapses duplicate official horse numbers.
    if len(ids)!=len(active):
        raise ValueError('duplicate horse number in official racecard')
    if set(evidence)!=ids:
        raise ValueError('complete evidence required for all active horses')
    runners=[];names={}
    for idx,horse in enumerate(active,1):
        number=str(horse['horse_no'])
        entry=deepcopy(evidence[number])
        if not isinstance(entry,dict) or not entry.get('horse_id') or not entry.get('history'):
            raise ValueError('real horse identity and prior history required')
        if not isinstance(entry['history'],list):
            raise ValueError('history must be list')
        if not entry.get('source_url') or not entry.get('available_at'):
            raise ValueError('horse evidence provenance required')
        if timestamp(entry['available_at'])>locked:
            raise ValueError('horse evidence from future')
        # A timely evidence envelope can still contain post-cutoff observations.
        # Refuse known observation timestamps after the prediction lock.
        for observation in entry['history']:
            if not isinstance(observation, dict):
                raise ValueError('history observation must be mapping')
            # A dated race alone does not prove when its result became public.
            # Require an explicit per-observation availability timestamp.
            if not observation.get('available_at'):
                raise ValueError('history observation availability timestamp required')
            # A published observation cannot predate the event it describes.
            # Otherwise a future race result could be backdated into training.
            if observation.get('occurred_at') and timestamp(observation['available_at']) < timestamp(observation['occurred_at']):
                raise ValueError('history availability precedes occurrence')
            for field in ('available_at', 'captured_at', 'observed_at', 'race_date', 'off_at', 'occurred_at'):
                value = observation.get(field)
                if value is not None and timestamp(value)>locked:
                    raise ValueError('history observation from future: ' + field)
        # Contract validation uses race off-time as cutoff; publication is locked earlier.
        # Check every optional runner feature against the actual prediction lock.
        for feature in ('state', 'style', 'workout', 'condition', 'jockey',
                        'sectional', 'ban_ei', 'jump'):
            feature_data = entry.get(feature)
            if feature_data is None:
                continue
            if not isinstance(feature_data, dict) or not feature_data.get('available_at'):
                raise ValueError('feature availability timestamp required: ' + feature)
            if timestamp(feature_data['available_at']) > locked:
                raise ValueError('feature from future relative to prediction lock: ' + feature)
            # A backdated availability stamp must not conceal a later observation.
            for field in ('occurred_at', 'captured_at', 'observed_at'):
                value = feature_data.get(field)
                if value is None:
                    continue
                if timestamp(value) > locked:
                    raise ValueError('feature observation from future: ' + feature + '.' + field)
                if timestamp(feature_data['available_at']) < timestamp(value):
                    raise ValueError('feature availability precedes occurrence: ' + feature)
        # Evidence must not overwrite racecard identities or the assigned barrier.
        reserved = {'horse_no', 'frame_no', 'barrier_no', 'race_id', 'mode', 'schema'}
        overlap = reserved.intersection(entry)
        if overlap:
            raise ValueError('horse evidence overrides racecard fields: ' + ','.join(sorted(overlap)))
        horse_id=entry.pop('horse_id')
        entry.pop('source_url');entry.pop('available_at')
        if horse_id in names:
            raise ValueError('duplicate horse identity')
        names[horse_id]=horse['horse_name']
        runners.append({'horse_id':horse_id,'horse_no':horse['horse_no'],
                        'frame_no':horse['frame_no'],'barrier_no':idx,
                        'carried_weight':entry.pop('carried_weight'),
                        'history':entry.pop('history'),**entry})
    raw={'schema':'prism.engine.raw/v1','mode':'PRE_AVAILABLE',
         'race':{'race_id':card['race_id'],'venue':venue,'surface':surface,
                 'distance_m':distance_m,'direction':direction,
                 'class_rating':class_rating,'cutoff':card['off_at'],
                 'barrier_count':barrier_count},
         'runners':runners,
         'source':{'source_id':card['official_url'],'available_at':card['captured_at'],
                   'content_hash':''}}
    raw['source']['content_hash']=digest({k:v for k,v in raw.items() if k!='source'})
    validate(raw)
    return raw,names
