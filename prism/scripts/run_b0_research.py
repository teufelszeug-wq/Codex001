"""Sequential historical research; source metadata is NOT PIT-certified."""
import argparse
from collections import Counter,defaultdict
from itertools import groupby
import json
import math
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/research'))
from b0_worker import CONFIG,digest

def history_updates(race):
    started=[x for x in race['results'] if x['status'] not in ('取消','除外','取止','競走除外')]
    n=len(started)
    if n<2:return []
    rank={x['number']:x['rank'] for x in started if x['rank'] is not None}
    return [(h['identity'],{'date':race['date'],'start':race['start'],'surface':race['surface'],
             'score':100*(n-rank[h['number']])/(n-1)}) for h in race['entrants']
            if h['number'] in rank and 1<=rank[h['number']]<=n]

def run(january,bootstrap,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    if any(r['date']>='20260101' for r in bootstrap):raise ValueError('bootstrap leakage')
    if len({r['race_id'] for r in january})!=len(january):raise ValueError('duplicate race')
    history=defaultdict(list)
    for r in sorted(bootstrap,key=lambda x:(x['date'],x['start'],x['race_id'])):
        for identity,row in history_updates(r):history[identity].append(row)
    worker=Path(__file__).resolve().parents[1]/'src/research/b0_worker.py'
    proc=subprocess.Popen([sys.executable,str(worker)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    totals=Counter();losses=[];briers=[];races=[];chain='0'*64
    try:
        ready=json.loads(proc.stdout.readline())
        if ready!={'ready':True,'file_open_denied':True,'network_denied':True}:raise RuntimeError('isolation unavailable')
        with (out/'predictions.jsonl').open('x') as pf,(out/'evaluations.jsonl').open('x') as ef,(out/'events.jsonl').open('x') as events:
            def emit(kind,payload):
                nonlocal chain
                record={'event':kind,'payload':payload,'previous_hash':chain};chain=digest(record);record['hash']=chain
                events.write(json.dumps(record,ensure_ascii=False)+'\n');events.flush()
            for _,group in groupby(sorted(january,key=lambda r:(r['date'],r['start'],r['race_id'])),lambda r:(r['date'],r['start'])):
                batch=list(group);locked=[]
                for r in batch:
                    request={k:r[k] for k in ('race_id','date','start','surface')}
                    request['runners']=[{'horse_no':h['number'],'history':history[h['identity']]} for h in sorted(r['entrants'],key=lambda x:x['number'])]
                    proc.stdin.write(json.dumps(request)+'\n');proc.stdin.flush();response=json.loads(proc.stdout.readline())
                    if 'error' in response:raise RuntimeError(response['error'])
                    pred=response['prediction'];pf.write(json.dumps(pred,ensure_ascii=False)+'\n');pf.flush()
                    emit('PREDICTION_LOCK',{'race_id':r['race_id'],'prediction_hash':pred['prediction_hash']});locked.append((r,pred))
                for r,pred in locked:
                    winners=[str(x['number']) for x in r['results'] if x['rank']==1]
                    if not winners or any(w not in pred['p_win'] or w not in r['win_payouts'] for w in winners):raise ValueError('unsettleable race')
                    pick=pred['pick'];status=next(x['status'] for x in r['results'] if x['number']==pick)
                    refund=100 if status in ('取消','除外','競走除外') else 0
                    payout=0 if refund else r['win_payouts'].get(str(pick),0)
                    loss=-sum(math.log(max(pred['p_win'][w],1e-12)) for w in winners)/len(winners)
                    brier=sum((p-(1/len(winners) if h in winners else 0))**2 for h,p in pred['p_win'].items())
                    row={'race_id':r['race_id'],'prediction_hash':pred['prediction_hash'],'stake_yen':100,'payout_excluding_refund_yen':payout,
                         'refund_yen':refund,'profit_yen':payout+refund-100,'log_loss':loss,'brier':brier}
                    ef.write(json.dumps(row)+'\n');ef.flush();emit('RESULT_REVEAL',{'race_id':r['race_id'],'evaluation_hash':digest(row)})
                    for k in ('stake_yen','payout_excluding_refund_yen','refund_yen','profit_yen'):totals[k]+=row[k]
                    totals['hits']+=str(pick) in winners;totals['cold_start_runners']+=len(pred['cold_start_horse_nos'])
                    losses.append(loss);briers.append(brier);races.append(r['race_id'])
                for r,_ in locked:
                    for identity,row in history_updates(r):history[identity].append(row)
                    emit('HISTORY_UPDATE',{'race_id':r['race_id']})
    finally:
        proc.stdin.close();proc.wait(timeout=10);proc.stdout.close()
    effective=totals['stake_yen']-totals['refund_yen']
    report={'status':'EXECUTED_RESEARCH_NOT_STRICT_PIT','races':len(races),'authorities':dict(Counter(r.split('|')[0] for r in races)),
            'config':CONFIG,'config_hash':digest(CONFIG),'settlement':dict(totals),'refund_excluded_roi':totals['payout_excluding_refund_yen']/effective,
            'log_loss':sum(losses)/len(losses),'brier':sum(briers)/len(briers),'terminal_hash':chain,
            'strict_pit':False,'phase_b_complete':False,'limitations':['reconstructed entrant metadata','provisional/composite identities','unknown historical availability','no speed/class normalization','cold-start explicit prior','not full PRISM']}
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--january',required=True);p.add_argument('--bootstrap',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    print(json.dumps(run(json.loads(Path(a.january).read_text()),json.loads(Path(a.bootstrap).read_text()),a.out),ensure_ascii=False,indent=2))
