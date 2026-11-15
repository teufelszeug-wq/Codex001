"""PRISM pre-publication payload gate; not a Git-history proof."""
from datetime import datetime

def validate(doc):
    errors=[]
    for field in ('race_id','saved_at','off_at','source_refs','records','version'):
        if field not in doc: errors.append('missing:'+field)
    if errors: return errors
    if not isinstance(doc['race_id'],str) or not doc['race_id'].strip(): errors.append('invalid:race_id')
    if type(doc['version']) is not int or doc['version']<1: errors.append('invalid:version')
    try:
        saved=datetime.fromisoformat(doc['saved_at']); off=datetime.fromisoformat(doc['off_at'])
        if saved.tzinfo is None or off.tzinfo is None or saved.utcoffset() is None or off.utcoffset() is None or saved>=off: errors.append('invalid:pre_off_time')
    except (TypeError,ValueError): errors.append('invalid:timestamps')
    if not isinstance(doc['source_refs'],list) or not doc['source_refs'] or any(not isinstance(x,str) or not x.strip() for x in doc['source_refs']): errors.append('invalid:source_refs')
    records=doc['records']
    if not isinstance(records,list) or not records: return errors+['invalid:records']
    seen=set()
    for i,r in enumerate(records):
        prefix=f'record[{i}]'
        if not isinstance(r,dict): errors.append(prefix+':not_object'); continue
        fid=r.get('forecaster_id')
        if not isinstance(fid,str) or not fid.strip(): errors.append(prefix+':forecaster_id')
        elif fid.strip() in seen: errors.append(prefix+':duplicate_forecaster_id')
        else: seen.add(fid.strip())
        if r.get('decision')=='abstain': continue
        if r.get('decision')!='bet': errors.append(prefix+':decision'); continue
        bets=r.get('bets')
        if not isinstance(bets,list) or not bets: errors.append(prefix+':bets'); continue
        for j,b in enumerate(bets):
            if not isinstance(b,dict) or not isinstance(b.get('horse_name'),str) or not b['horse_name'].strip(): errors.append(f'{prefix}:bet[{j}]:horse_name')
            if not isinstance(b,dict) or type(b.get('stake_yen')) is not int or b['stake_yen']<100 or b['stake_yen']%100: errors.append(f'{prefix}:bet[{j}]:stake_yen')
    return errors
