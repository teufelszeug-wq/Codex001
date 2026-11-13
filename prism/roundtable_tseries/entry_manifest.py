"""Source-linked PRISM race-entry identity gate.

Accepts official entries with scratched/excluded horses and non-contiguous
start numbers. Completeness and source binding are structural, not
authentication of a remote JRA/NAR publication time.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json

class EntryGateError(ValueError):
    pass

def canonical_sha(data):
    return sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def instant(ts):
    try:
        dt=datetime.fromisoformat(ts.replace('Z','+00:00'))
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError('timezone required')
        return dt.astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError) as exc:
        raise EntryGateError('INVALID_TIMEZONE_TIMESTAMP') from exc

def verify_entries(race,entries,official=None):
    for key in ('race_id','venue','race_no','surface','distance_m','start_at','source_url','source_retrieved_at','official_entry_count'):
        if race.get(key) is None or race.get(key)=='':
            raise EntryGateError('MISSING_RACE_FIELD:'+key)
    if race.get('prediction_mode')=='FORWARD':
        raise EntryGateError('FORWARD_NEEDS_EXTERNAL_TIME_ATTESTATION')
    if type(race['official_entry_count']) is not int or race['official_entry_count']!=len(entries):
        raise EntryGateError('ENTRY_COUNT_MISMATCH')
    retrieval=instant(race['source_retrieved_at'])
    kickoff=instant(race['start_at'])
    prior=0; names=set();active=[];inactive=[]
    for e in entries:
        n=e.get('number');name=e.get('name');status=e.get('status')
        if type(n) is not int or not prior<n<=30:
            raise EntryGateError('DUPLICATE_OR_OUT_OF_ORDER_NUMBER')
        prior=n
        if not isinstance(name,str) or not name.strip() or name in names:
            raise EntryGateError('DUPLICATE_OR_MISSING_NAME')
        names.add(name)
        if type(e.get('frame')) is not int or not 1<=e['frame']<=8:
            raise EntryGateError('INVALID_FRAME')
        if status not in ('STARTER','SCRATCHED','EXCLUDED'):
            raise EntryGateError('INVALID_STARTER_STATUS')
        if not e.get('source_url'):
            raise EntryGateError('ENTRY_SOURCE_MISSING')
        if official is not None and official.get(str(n))!={'name':name,'frame':e['frame'],'status':status}:
            raise EntryGateError('OFFICIAL_RUNNER_MISMATCH')
        if status=='STARTER':
            if not e.get('past_fact') or not e.get('evidence'):
                raise EntryGateError('RUNNER_SOURCE_MISSING')
            active.append(n)
        else:
            if not e.get('status_reason') or not e.get('status_source_url'):
                raise EntryGateError('SCRATCH_SOURCE_MISSING')
            inactive.append(n)
    if not active:raise EntryGateError('NO_ACTIVE_RUNNERS')
    if official is not None and set(official)!={str(e['number']) for e in entries}:
        raise EntryGateError('OFFICIAL_ENTRY_SET_MISMATCH')
    snapshot=[{k:e[k] for k in ('number','frame','name','status')} for e in entries]
    return {'status':'STRUCTURE_PASS','entries':len(entries),'active_numbers':active,'inactive_numbers':inactive,
            'roster_hash':canonical_sha(snapshot),
            'source_temporal_class':'RETROSPECTIVE_ONLY' if retrieval>=kickoff else 'RETRIEVED_EARLY_NOT_CERTIFIED',
            'externally_authenticated':False}

def verify_conversation(entries,turns):
    starters=[e for e in entries if e['status']=='STARTER']
    excluded=[e for e in entries if e['status']!='STARTER']
    intros=[t.get('horse') for t in turns if t.get('stage')=='HORSE_INTRO']
    core=[t.get('horse') for t in turns if t.get('stage')=='HORSE_CORE']
    notices=[t.get('horse') for t in turns if t.get('stage')=='SCRATCH_NOTICE']
    expected=[e['number'] for e in starters]
    errors=[]
    if intros!=expected:errors.append('ACTIVE_SEQUENCE_OMISSION')
    if sorted(core)!=expected:errors.append('CORE_DIAGNOSIS_OMISSION_OR_DUPLICATION')
    if sorted(notices)!=[e['number'] for e in excluded]:
        errors.append('CANCELLATION_NOTICE_OMISSION')
    dictionary={e['number']:e['name'] for e in entries}
    for t in turns:
        if t.get('stage') in ('HORSE_INTRO','HORSE_CORE','SCRATCH_NOTICE'):
            n=t.get('horse')
            if n not in dictionary or f"{n}番{dictionary[n]}" not in t.get('text',''):
                errors.append('HORSE_NUMBER_AND_NAME_REQUIRED')
    return {'status':'PASS' if not errors else 'FAIL','errors':sorted(set(errors)),
            'assessed':len(core),'expected_starters':len(expected),
            'excluded_notified':len(notices),'expected_excluded':len(excluded)}
