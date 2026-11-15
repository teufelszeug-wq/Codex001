"""Fail-closed real-race audit: never count CI or post-off predictions as pre-off."""
import argparse
import json
from datetime import datetime
from pathlib import Path

REQUIRED = ('race_id','version','saved_at','off_at','source_refs','records')
def audit(targets, forecast_files):
    by_id = {r['race_id']:r for r in targets['targets']}
    if len(by_id)!=len(targets['targets']):
        raise ValueError('duplicate target race IDs')
    rows={rid:{'race_id':rid,'pre_off_verified':False,'reason':'NO_VERIFIED_PRE_OFF_FORECAST'} for rid in by_id}
    for file in forecast_files:
        try:
            doc=json.loads(Path(file).read_text(encoding='utf-8'))
            if any(k not in doc for k in REQUIRED):raise ValueError('required forecast fields missing')
            rid=doc['race_id']
            if rid not in by_id:continue
            saved=datetime.fromisoformat(doc['saved_at'])
            off=datetime.fromisoformat(doc['off_at'])
            expected=datetime.fromisoformat(by_id[rid]['off_at'])
            if not saved.tzinfo or not off.tzinfo or saved>=off or off!=expected:
                raise ValueError('not a verified pre-off timestamp')
            if not isinstance(doc['version'],int) or doc['version']<1 or not doc['source_refs'] or not doc['records']:
                raise ValueError('missing version, source, or predictions')
            # A locally written timestamp is insufficient proof: a pre-off
            # Git commit or external immutable provenance must be verified.
            rows[rid]['reason']='TIMESTAMP_PRESENT_BUT_EXTERNAL_PRE_OFF_PROOF_REQUIRED'
        except (OSError,ValueError,TypeError,KeyError) as exc:
            if isinstance(exc,ValueError) and 'duplicate target' in str(exc):raise
            # Invalid files never increase completion counts.
            pass
    return {'schema':'prism.real_race_audit/v1','target_count':len(by_id),
            'verified_pre_off_count':sum(r['pre_off_verified'] for r in rows.values()),
            'status':'CRITICAL' if not any(r['pre_off_verified'] for r in rows.values()) else 'INCOMPLETE',
            'races':list(rows.values())}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--targets',type=Path,required=True)
    p.add_argument('--forecast',type=Path,action='append',default=[])
    a=p.parse_args()
    print(json.dumps(audit(json.loads(a.targets.read_text(encoding='utf-8')),a.forecast),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
