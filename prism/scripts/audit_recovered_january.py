"""Recheck stored research evidence. Never runs a forecast or certifies PIT."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

def digest(obj):
    return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def audit_run(root):
    root=Path(root); errors=[]
    rows=list(csv.DictReader((root/'race_ledger.csv').open(encoding='utf-8-sig')))
    by_id={x['race_id']:x for x in rows}
    if len(by_id)!=len(rows):errors.append('duplicate_race_id')
    events=[json.loads(line) for p in sorted(root.glob('events_*.jsonl')) for line in p.read_text().splitlines()]
    previous='0'*64; stages={}; prediction_count=review_count=0
    for i,event in enumerate(events):
        if event['seq']!=i or event['previous_hash']!=previous:errors.append('event_chain_link')
        if digest({k:v for k,v in event.items() if k!='hash'})!=event['hash']:errors.append('event_hash')
        previous=event['hash'];payload=event['payload'];rid=payload.get('race_id');kind=event['event']
        if kind=='PREDICTION_LOCK':
            if rid in stages:errors.append('duplicate_prediction')
            stages[rid]='PREDICTION_LOCK'
            filename=payload['file']
            if Path(filename).name!=filename:raise ValueError('unsafe prediction filename')
            pred=json.loads((root/'predictions'/filename).read_text())
            expected=digest({k:v for k,v in pred.items() if k!='lock_hash'})
            if pred['lock_hash']!=expected or payload['hash']!=expected or pred['race_id']!=rid:errors.append('prediction_hash')
            if len(pred['tickets'])!=1 or pred['tickets'][0]['stake_yen']!=100:errors.append('ticket_policy')
            probs=pred['probabilities']['win']
            if abs(sum(probs.values())-1)>1e-8 or any(not 0<=p<=1 for p in probs.values()):errors.append('probability_mass')
            prediction_count+=1
        elif kind=='RESULT_REVEAL':
            if stages.get(rid)!='PREDICTION_LOCK':errors.append('result_before_lock')
            stages[rid]='RESULT_REVEAL'
        elif kind=='REVIEW_AND_LEARN':
            if stages.get(rid)!='RESULT_REVEAL':errors.append('review_before_result')
            stages[rid]='REVIEW_AND_LEARN';review_count+=1
    reviews=[json.loads(p.read_text()) for p in sorted((root/'reviews').glob('*.json'))]
    reviews_by_id={r['race_id']:r for r in reviews}
    predictions_by_id={json.loads(p.read_text())['race_id']:json.loads(p.read_text()) for p in (root/'predictions').glob('*.json')}
    for e in events:
        if e['event']=='REVIEW_AND_LEARN':
            r=reviews_by_id[e['payload']['race_id']]
            if digest(r)!=e['payload']['review_hash']:errors.append('review_hash')
            if r['prediction_hash']!=predictions_by_id[r['race_id']]['lock_hash']:errors.append('review_prediction_link')
    if set(stages)!=set(by_id) or set(reviews_by_id)!=set(by_id):errors.append('race_coverage')
    if any(v!='REVIEW_AND_LEARN' for v in stages.values()):errors.append('incomplete_race')
    totals=Counter()
    for row in rows:
        for k in ('stake_yen','payout_yen','refund_yen','profit_yen'):
            value=int(row[k]);totals[k]+=value
            if value!=int(reviews_by_id[row['race_id']][k]):errors.append('ledger_review_mismatch')
        if int(row['stake_yen'])!=100:errors.append('stake_not_100')
        # Legacy payout_yen already includes refunded stakes.
        if int(row['profit_yen'])!=int(row['payout_yen'])-int(row['stake_yen']):errors.append('settlement_identity')
    effective=totals['stake_yen']-totals['refund_yen']
    return {'status':'VERIFIED_STORED_RESEARCH' if not errors else 'FAIL','races':len(rows),
            'authority_counts':dict(Counter(x['authority'] for x in rows)), 'predictions':prediction_count,
            'reviews':review_count,'events':len(events),'terminal_hash':previous,'errors':dict(Counter(errors)),
            'settlement':dict(totals),'legacy_payout_includes_refund':True,
            'refund_excluded_roi':(totals['payout_yen']-totals['refund_yen'])/effective if effective else None,
            'forecast_rerun':False,'strict_pit_certified':False,'b0_reproduced':False}

def census(root):
    root=Path(root);base=root/'data/replay_202601';nar=base/'nar/candidates_NOT_PIT_APPROVED'
    races=[json.loads(x) for x in (nar/'races.jsonl').read_text().splitlines()]
    horses=[json.loads(x) for x in (nar/'horses.jsonl').read_text().splitlines()]
    key=lambda x:(x['競走年月日'],x['競馬場'],x['レース番号'])
    race_keys={key(x) for x in races};runner_keys=[(*key(x),x['馬番']) for x in horses]
    return {'nar_races':len(races),'nar_runner_rows':len(horses),'duplicate_races':len(races)-len(race_keys),
            'duplicate_runners':len(runner_keys)-len(set(runner_keys)),
            'orphan_runners':sum(key(x) not in race_keys for x in horses),
            'frame_and_horse_separate':all('枠番' in x and '馬番' in x for x in horses),
            'temporal_class':'UNKNOWN_TIMESTAMP','approved_b0_rows':0,
            'reason':'No per-row pre-race availability proof; candidates explicitly NOT_PIT_APPROVED',
            'runs':{n:audit_run(base/n) for n in ('ordinal_revalidated_v4','next_day_sensitivity_v4')}}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--report',required=True);a=p.parse_args()
    report=census(a.root);Path(a.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(1 if any(r['errors'] for r in report['runs'].values()) else 0)
