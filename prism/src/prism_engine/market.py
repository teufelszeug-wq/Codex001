"""Post-lock Value, exact joint ticket probabilities and fixed-100-yen selection."""
from itertools import combinations
from .contracts import fields,numeric,timestamp,digest

TYPES={'WIN':1,'PLACE':1,'QUINELLA':2,'EXACTA':2,'WIDE':2,'TRIO':3,'TRIFECTA':3,'FRAME':2}
UNORDERED={'QUINELLA','WIDE','TRIO','FRAME'}

def ticket_key(bet_type,legs):
    if bet_type not in TYPES or len(legs)!=TYPES[bet_type] or any(not isinstance(x,str) or not x for x in legs):raise ValueError('ticket shape rejected')
    if bet_type!='FRAME' and len(set(legs))!=len(legs):raise ValueError('duplicate ticket leg')
    parts=tuple(sorted(legs)) if bet_type in UNORDERED else tuple(legs)
    return digest({'type':bet_type,'legs':parts})

def hit(bet_type,legs,order,frames,place_slots):
    if bet_type=='WIN':return order[0]==legs[0]
    if bet_type=='PLACE':return legs[0] in order[:place_slots]
    if bet_type=='QUINELLA':return set(legs)==set(order[:2])
    if bet_type=='EXACTA':return tuple(legs)==tuple(order[:2])
    if bet_type=='WIDE':return set(legs)<=set(order[:3])
    if bet_type=='TRIO':return set(legs)==set(order[:3])
    if bet_type=='TRIFECTA':return tuple(legs)==tuple(order[:3])
    if bet_type=='FRAME':return sorted(legs)==sorted(frames[x] for x in order[:2])
    raise ValueError('unsupported ticket')

def value_candidates(lock,market,config):
    if lock['lock_hash']!=digest({k:v for k,v in lock.items() if k!='lock_hash'}):raise ValueError('prediction lock changed')
    fields(market,{'race_id','prediction_hash','observed_at','opened_at','quotes','place_slots'},
           {'race_id','prediction_hash','observed_at','opened_at','quotes','place_slots'})
    if market['race_id']!=lock['race_id'] or market['prediction_hash']!=lock['lock_hash']:raise ValueError('market lock identity mismatch')
    observed=timestamp(market['observed_at']);opened=timestamp(market['opened_at'])
    if not observed<=opened<=timestamp(lock['cutoff']) or opened<timestamp(lock['locked_at']):raise ValueError('market phase/time rejected')
    if (opened-observed).total_seconds()>config['max_quote_age_seconds']:raise ValueError('stale odds')
    slots=market['place_slots']
    if type(slots) is not int or not 1<=slots<=min(3,len(lock['win'])):raise ValueError('explicit authority place slots required')
    frames=lock['frames'];ids=set(lock['win']);seen=set();candidates=[]
    for quote in market['quotes']:
        fields(quote,{'bet_type','legs','odds_low','odds_high'}, {'bet_type','legs','odds_low','odds_high'})
        kind=quote['bet_type'];legs=quote['legs'];key=ticket_key(kind,legs)
        if key in seen:raise ValueError('duplicate quoted ticket')
        seen.add(key)
        if kind=='FRAME':
            if any(x not in frames.values() for x in legs):raise ValueError('unknown frame')
            if legs[0]==legs[1] and list(frames.values()).count(legs[0])<2:raise ValueError('impossible same-frame ticket')
        elif not set(legs)<=ids:raise ValueError('unknown horse ticket')
        low=numeric(quote['odds_low'],1,100000000);high=numeric(quote['odds_high'],low,100000000)
        probability=sum(p for order,p in lock['rank_distribution'] if hit(kind,legs,order,frames,slots))
        probability=min(1.,max(0.,probability));ev=probability*low-1
        candidates.append({'key':key,'bet_type':kind,'legs':sorted(legs) if kind in UNORDERED else list(legs),
                           'probability':probability,'decimal_odds':low,'quoted_high':high,'fair_odds':1/probability if probability else None,
                           'gross_return_ratio':ev+1,'net_ev':ev,'expected_profit_yen':100*ev,'stake_yen':100,
                           'status':'REFERENCE','nvalue_longshot':low>=config['longshot_odds_min'] and ev>config['min_net_ev']})
    win_quotes={c['legs'][0]:c['decimal_odds'] for c in candidates if c['bet_type']=='WIN'}
    inverse_sum=sum(1/o for o in win_quotes.values()) if set(win_quotes)==ids else None
    for c in candidates:
        proxy=(1/c['decimal_odds'])/inverse_sum if c['bet_type']=='WIN' and inverse_sum else None
        c['normalized_market_proxy']=proxy
        c['relative_market_value']=c['probability']/proxy if proxy else None
        c['market_proxy_is_true_probability']=False
    return sorted(candidates,key=lambda c:(-c['expected_profit_yen'],c['key']))

def optimize(candidates,config):
    # Exact search over an explicitly bounded pool; no Kelly stake expansion.
    cap=config['candidate_pool_limit'];points=config['budget_yen']//100
    if type(cap) is not int or not 1<=cap<=24 or type(config['max_points']) is not int or not 0<=config['max_points']<=6:raise ValueError('optimizer size limit')
    if type(config['budget_yen']) is not int or config['budget_yen']<0 or config['budget_yen']%100:raise ValueError('budget must be 100-yen units')
    if type(config['max_exposure_per_leg']) is not int or config['max_exposure_per_leg']<1:raise ValueError('invalid exposure cap')
    eligible=[x for x in candidates if x['net_ev']>config['min_net_ev']][:cap]
    best=();best_gain=0.
    for count in range(1,min(points,config['max_points'],len(eligible))+1):
        for subset in combinations(eligible,count):
            counts={};valid=True
            for ticket in subset:
                for leg in set(ticket['legs']):
                    # Frames and horses are separate namespaces.
                    key=('FRAME' if ticket['bet_type']=='FRAME' else 'HORSE',leg)
                    counts[key]=counts.get(key,0)+1
                    if counts[key]>config['max_exposure_per_leg']:valid=False
            if not valid:continue
            gain=sum(c['expected_profit_yen'] for c in subset)
            if gain>best_gain+1e-12:best=subset;best_gain=gain
    return {'tickets':[dict(t,status='CANDIDATE') for t in best],'stake_yen':100*len(best),
            'objective':'MAX_SUM_EXPECTED_PROFIT_WITHIN_POOL_NOT_RISK_OPTIMAL',
            'expected_profit_yen':best_gain,'pool_limit':cap,'pool_truncated':len([c for c in candidates if c['net_ev']>config['min_net_ev']])>cap,
            'decision':'CANDIDATES' if best else 'NO_BET'}

def settle(plan,result,race_id,cutoff):
    fields(result,{'race_id','prediction_hash','available_at','payouts','refund_keys','complete_bet_types'},
           {'race_id','prediction_hash','available_at','payouts','refund_keys','complete_bet_types'})
    if plan.get('race_id')!=race_id or plan.get('prediction_hash')!=result['prediction_hash']:raise ValueError('settlement prediction binding mismatch')
    if plan.get('plan_hash')!=digest({k:v for k,v in plan.items() if k!='plan_hash'}):raise ValueError('plan hash mismatch')
    keys=[t['key'] for t in plan['tickets']]
    if len(keys)!=len(set(keys)) or plan['stake_yen']!=100*len(keys):raise ValueError('duplicate tickets or plan total mismatch')
    if result['race_id']!=race_id or timestamp(result['available_at'])<timestamp(cutoff):raise ValueError('result identity/time rejected')
    payouts={}
    for q in result['payouts']:
        fields(q,{'bet_type','legs','payout_per_100_yen'}, {'bet_type','legs','payout_per_100_yen'})
        key=ticket_key(q['bet_type'],q['legs']);value=q['payout_per_100_yen']
        if type(value) is not int or value<0 or key in payouts:raise ValueError('official payout rejected')
        payouts[key]=value
    refunds=result['refund_keys']
    if len(refunds)!=len(set(refunds)) or set(refunds)&set(payouts):raise ValueError('refund/payout conflict')
    rows=[]
    for t in plan['tickets']:
        if t['stake_yen']!=100 or t['key']!=ticket_key(t['bet_type'],t['legs']):raise ValueError('fixed stake or key changed')
        if t['bet_type'] not in result['complete_bet_types']:raise ValueError('official pool result incomplete')
        refund=100 if t['key'] in refunds else 0;payout=0 if refund else payouts.get(t['key'],0)
        rows.append({'key':t['key'],'stake_yen':100,'refund_yen':refund,'payout_yen':payout,'profit_yen':payout+refund-100})
    gross=sum(x['stake_yen'] for x in rows);refund=sum(x['refund_yen'] for x in rows);payout=sum(x['payout_yen'] for x in rows);effective=gross-refund
    return {'rows':rows,'gross_stake_yen':gross,'refund_yen':refund,'effective_stake_yen':effective,
            'payout_yen':payout,'profit_yen':payout-effective,'roi':payout/effective if effective else None}
