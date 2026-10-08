"""B0 research baseline: prior ordinal ability only; no current result or market."""
import hashlib
import json
import math
import sys
from datetime import datetime
from isolation import restrict_io

CONFIG={'version':'B0-ordinal-ability-research-1','half_life_days':180,
        'temperature':18,'cold_start_prior':50,'surface_history_separated':True,
        'stake_yen':100,'same_time_batch_lock':True,'strict_pit':False}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def predict(request):
    if set(request)!={'race_id','date','start','surface','runners'}:raise ValueError('unexpected request field')
    numbers=[];scores={};cold=[]
    target=datetime.strptime(request['date'],'%Y%m%d')
    for runner in request['runners']:
        if set(runner)!={'horse_no','history'}:raise ValueError('unexpected runner field')
        number=runner['horse_no']
        if type(number) is not int or number<1 or number in numbers:raise ValueError('invalid number')
        numbers.append(number);weighted=mass=0.
        for row in runner['history']:
            if set(row)!={'date','start','surface','score'}:raise ValueError('unexpected history field')
            if (row['date'],row['start'])>=(request['date'],request['start']):raise ValueError('future history')
            score=row['score']
            if not math.isfinite(score) or not 0<=score<=100:raise ValueError('invalid score')
            if row['surface']!=request['surface']:continue
            days=(target-datetime.strptime(row['date'],'%Y%m%d')).days
            weight=0.5**(days/CONFIG['half_life_days']);weighted+=score*weight;mass+=weight
        scores[str(number)]=weighted/mass if mass else CONFIG['cold_start_prior']
        if not mass:cold.append(number)
    if len(numbers)<2:raise ValueError('insufficient runners')
    maximum=max(scores.values());weights={k:math.exp((v-maximum)/CONFIG['temperature']) for k,v in scores.items()}
    total=sum(weights.values());probs={k:v/total for k,v in weights.items()}
    pick=min(probs,key=lambda k:(-probs[k],int(k)))
    out={'race_id':request['race_id'],'p_win':probs,'scores':scores,'cold_start_horse_nos':cold,
         'pick':int(pick),'stake_yen':100,'input_hash':digest(request),'config_hash':digest(CONFIG),
         'mode':'HISTORICAL_RECONSTRUCTION_NOT_PIT','model_version':CONFIG['version']}
    out['prediction_hash']=digest(out);return out

if __name__=='__main__':
    datetime.strptime('20260101','%Y%m%d')
    import socket
    restrict_io()
    try:open('/etc/passwd');raise RuntimeError('file isolation failed')
    except PermissionError:pass
    try:socket.socket();raise RuntimeError('network isolation failed')
    except PermissionError:pass
    print(json.dumps({'ready':True,'file_open_denied':True,'network_denied':True}),flush=True)
    for line in sys.stdin:
        try:response={'prediction':predict(json.loads(line))}
        except Exception as exc:response={'error':str(exc)}
        print(json.dumps(response,ensure_ascii=False,allow_nan=False),flush=True)
