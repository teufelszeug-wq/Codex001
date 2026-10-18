"""Validate a proposed B0 input; never infer availability from a result page."""
import hashlib
import json
from datetime import datetime
from math import isfinite

PROHIBITED={'finish_position','result_time','result_margin','result_last3f','payout',
            'winning_horse','post_result_revision','odds','popularity','market','result','results','win_payouts'}
RACE_FIELDS={'race_id','authority','date','venue','race_no','surface','distance','cutoff','provenance','runners'}
RUNNER_FIELDS={'race_id','runner_key','horse_no','carried_weight','frame_no','horse_id','horse_name',
               'jockey_id','jockey_name','trainer_id','trainer_name','sex','age','identity_status','provenance'}
PROVENANCE_FIELDS={'temporal_class','source_id','content_hash','available_at'}

def instant(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('timezone required')
    return parsed

def forbidden(value):
    if isinstance(value,dict):
        return bool(PROHIBITED.intersection(value)) or any(forbidden(v) for v in value.values())
    if isinstance(value,list):return any(forbidden(v) for v in value)
    return False

def validate(dataset):
    errors=[];race_ids=set();runner_keys=set()
    if set(dataset)-{'races'}:errors.append('unrecognized_dataset_fields')
    if forbidden(dataset):errors.append('prohibited_prediction_input')
    if not dataset.get('races'):errors.append('empty_dataset')
    for race in dataset.get('races',[]):
        rid=race.get('race_id');race_errors=[]
        if set(race)-RACE_FIELDS:race_errors.append('unrecognized_race_fields')
        for field in ('race_id','authority','date','venue','race_no','surface','distance'):
            if race.get(field) in (None,''):race_errors.append('missing_race_'+field)
        if rid in race_ids:race_errors.append('duplicate_race')
        race_ids.add(rid)
        if not race.get('runners'):race_errors.append('missing_runners')
        try:cutoff=instant(race['cutoff'])
        except (KeyError,ValueError,TypeError,AttributeError):cutoff=None;race_errors.append('invalid_cutoff')
        for item in [race]+race.get('runners',[]):
            evidence=item.get('provenance',{})
            if set(evidence)-PROVENANCE_FIELDS:race_errors.append('unrecognized_provenance_fields')
            if evidence.get('temporal_class') not in ('PRE_CERTIFIED','PRE_AVAILABLE'):
                race_errors.append('unapproved_temporal_class')
            if not evidence.get('source_id') or not evidence.get('content_hash'):
                race_errors.append('missing_source_identity')
            try:
                available=instant(evidence['available_at'])
                if cutoff is None or available>cutoff:race_errors.append('future_input')
            except (KeyError,ValueError,TypeError,AttributeError):race_errors.append('unknown_availability')
        numbers=set()
        for runner in race.get('runners',[]):
            if set(runner)-RUNNER_FIELDS:race_errors.append('unrecognized_runner_fields')
            for field in ('race_id','runner_key','horse_no','carried_weight'):
                if runner.get(field) in (None,''):race_errors.append('missing_runner_'+field)
            if runner.get('race_id')!=rid:race_errors.append('orphan_runner')
            key=(rid,runner.get('runner_key'))
            if key in runner_keys:race_errors.append('duplicate_runner')
            runner_keys.add(key)
            number=runner.get('horse_no')
            if type(number) is not int or number<1 or number in numbers:race_errors.append('invalid_horse_number')
            numbers.add(number)
            weight=runner.get('carried_weight')
            if type(weight) not in (int,float) or not isfinite(weight) or weight<=0:race_errors.append('invalid_carried_weight')
            if runner.get('identity_status')!='RESOLVED':race_errors.append('unresolved_identity')
        errors.extend({'race_id':rid,'reason':e} for e in sorted(set(race_errors)))
    raw=json.dumps(dataset,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    return {'status':'INPUT_STRUCTURE_PASS' if not errors else 'BLOCKED','errors':errors,
            'dataset_sha256':hashlib.sha256(raw).hexdigest(),'races':len(race_ids),
            'source_authenticity_verified':False,'b0_reproduced':False}
