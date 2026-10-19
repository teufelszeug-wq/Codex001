"""Coherent PL ticket probabilities and seeded Monte Carlo; temperature calibration."""
from itertools import permutations
from math import exp,log
import random
from .contracts import numeric,digest,timestamp,fields

def softmax(scores,temperature):
    numeric(temperature,.01,1000);m=max(scores.values())
    scaled={k:(v-m)/temperature for k,v in sorted(scores.items())}
    if min(scaled.values()) < -700:raise ValueError('temperature too sharp for supported PL precision')
    weights={k:exp(v) for k,v in scaled.items()};total=sum(weights.values())
    return {k:v/total for k,v in weights.items()}

def rank_probability(order,win):
    if len(order)!=len(set(order)):return 0.
    used=set();p=1.
    for horse in order:
        denominator=sum(value for key,value in win.items() if key not in used)
        p*=win[horse]/denominator;used.add(horse)
    return p

def distribution(win):
    n=len(win);count=min(3,n);rows=[(order,rank_probability(order,win)) for order in permutations(sorted(win),count)]
    if abs(sum(p for _,p in rows)-1)>1e-8:raise ValueError('rank mass violation')
    return rows

def marginals(win,rows):
    t2={k:0. for k in win};t3=t2.copy()
    for order,p in rows:
        for k in order[:2]:t2[k]+=p
        for k in order[:3]:t3[k]+=p
    for k in win:
        if not -1e-9<=win[k]<=t2[k]+1e-9 or not t2[k]<=t3[k]+1e-9<=1+2e-9:raise ValueError('nested probability violation')
    return {'win':win,'top2':t2,'top3':t3}

def simulate(win,runs,seed):
    if type(runs) is not int or not 1<=runs<=1000000 or type(seed) is not int:raise ValueError('simulation config rejected')
    rng=random.Random(seed);counts={k:0 for k in win};top2=counts.copy();top3=counts.copy();ids=sorted(win)
    for _ in range(runs):
        remaining=list(ids);order=[]
        for position in range(min(3,len(ids))):
            mass=sum(win[k] for k in remaining);u=rng.random()*mass;total=0.;selected=remaining[-1]
            for k in remaining:
                total+=win[k]
                if u<total:selected=k;break
            order.append(selected);remaining.remove(selected)
        counts[order[0]]+=1
        for k in order[:2]:top2[k]+=1
        for k in order[:3]:top3[k]+=1
    return {'runs':runs,'seed':seed,'win':{k:v/runs for k,v in counts.items()},
            'top2':{k:v/runs for k,v in top2.items()},'top3':{k:v/runs for k,v in top3.items()},
            'sampling_model':'PL_WITHOUT_REPLACEMENT'}

def scenario_joint(scenarios,scenario_weights,calibrated_win,uncalibrated_win):
    """Calibrate the mixture's first marginal, preserving conditional rank shape."""
    combined={}
    for label,win in scenarios.items():
        for order,p in distribution(win):combined[order]=combined.get(order,0.)+scenario_weights[label]*p
    rows=[(order,p*calibrated_win[order[0]]/uncalibrated_win[order[0]]) for order,p in sorted(combined.items())]
    if abs(sum(p for _,p in rows)-1)>1e-8:raise ValueError('scenario joint mass violation')
    return rows

def simulate_joint(rows,runs,seed):
    if type(runs) is not int or not 1<=runs<=1000000 or type(seed) is not int:raise ValueError('simulation config rejected')
    from bisect import bisect_left
    cumulative=[];total=0.
    ids=sorted({k for order,_ in rows for k in order});win={k:0 for k in ids};t2=win.copy();t3=win.copy()
    for _,p in rows:total+=p;cumulative.append(total)
    if abs(total-1)>1e-8:raise ValueError('sampling mass rejected')
    rng=random.Random(seed)
    for _ in range(runs):
        order=rows[min(len(rows)-1,bisect_left(cumulative,rng.random()*total))][0]
        win[order[0]]+=1
        for k in order[:2]:t2[k]+=1
        for k in order[:3]:t3[k]+=1
    return {'runs':runs,'seed':seed,'win':{k:v/runs for k,v in win.items()},
            'top2':{k:v/runs for k,v in t2.items()},'top3':{k:v/runs for k,v in t3.items()},
            'sampling_model':'CALIBRATED_PACE_MIXTURE_JOINT'}

def fit_calibration(rows,calibration_end,grid):
    if not rows:raise ValueError('calibration rows required')
    end=timestamp(calibration_end);seen=set()
    for row in rows:
        fields(row,{'race_id','outcome_available_at','probabilities','winners'}, {'race_id','outcome_available_at','probabilities','winners'})
        if row['race_id'] in seen or timestamp(row['outcome_available_at'])>end:raise ValueError('calibration chronology/duplicate')
        seen.add(row['race_id']);p=row['probabilities'];w=row['winners']
        if not p or abs(sum(p.values())-1)>1e-8 or not w or len(w)!=len(set(w)) or not set(w)<=set(p):raise ValueError('calibration outcomes rejected')
        # This PL/temperature implementation requires strictly positive mass.
        # Clipping distinct small probabilities to a shared floor silently
        # changes the model, even with identity temperature.
        for v in p.values():
            numeric(v,0,1)
            if v<=0:raise ValueError('strictly positive calibration probabilities required')
    best=None
    for t in grid:
        numeric(t,.05,20);loss=0.
        for row in rows:
            scores={k:log(p) for k,p in row['probabilities'].items()};scaled=softmax(scores,t)
            loss-=sum(log(scaled[w]) for w in row['winners'])/len(row['winners'])
        candidate=(loss/len(rows),t)
        if best is None or candidate<best:best=candidate
    if best is None:raise ValueError('temperature grid required')
    out={'method':'temperature-grid-v1','temperature':best[1],'training_log_loss':best[0],
         'trained_until':calibration_end,'training_race_ids':sorted(seen),'training_hash':digest(rows)}
    out['artifact_hash']=digest(out);return out

def apply_calibration(win,artifact,race_id,cutoff):
    if artifact is None:return win,'IDENTITY_NOT_FITTED'
    fields(artifact,{'method','temperature','training_log_loss','trained_until','training_race_ids','training_hash','artifact_hash'},
           {'method','temperature','training_log_loss','trained_until','training_race_ids','training_hash','artifact_hash'})
    if artifact['artifact_hash']!=digest({k:v for k,v in artifact.items() if k!='artifact_hash'}):raise ValueError('calibration hash mismatch')
    if race_id in artifact['training_race_ids'] or timestamp(artifact['trained_until'])>=timestamp(cutoff):raise ValueError('calibration target leakage')
    if artifact['method']!='temperature-grid-v1':raise ValueError('calibration method rejected')
    for value in win.values():
        numeric(value,0,1)
        if value<=0:raise ValueError('strictly positive calibration probabilities required')
    return softmax({k:log(v) for k,v in win.items()},artifact['temperature']),'FITTED_HISTORICAL'
