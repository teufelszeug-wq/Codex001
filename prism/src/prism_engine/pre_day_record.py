"""Provenance gate for pre-day predictions and post-race records."""
from datetime import datetime

def validate(record):
    required = ('race_id','horse_id','horse_name','predictor_id','source','saved_at','version','cutoff','stage')
    if any(not isinstance(record.get(k),str) or not record[k].strip() for k in required):
        raise ValueError('missing required provenance field')
    if record['stage'] not in ('PRE_DAY','DAY_DELTA','POST_RACE'):
        raise ValueError('invalid stage')
    def instant(k):
        try: t=datetime.fromisoformat(record[k])
        except ValueError: raise ValueError('invalid timestamp')
        if t.tzinfo is None or t.utcoffset() is None: raise ValueError('naive timestamp')
        return t
    saved,cutoff=instant('saved_at'),instant('cutoff')
    if record['stage']!='POST_RACE' and saved>=cutoff:
        raise ValueError('prediction saved at or after cutoff')
    if record['stage']=='POST_RACE' and saved<cutoff:
        raise ValueError('post-race record predates cutoff')
    if 'source_available_at' in record and instant('source_available_at')>saved:
        raise ValueError('source unavailable when saved')
    return dict(record)
