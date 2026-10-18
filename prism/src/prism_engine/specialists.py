"""Independent deterministic challenger interface, not a trained persona model."""
from .contracts import timestamp

def ability_recheck(raw,feature_output):
    out={}
    for runner in raw['runners']:
        horse=runner['horse_id']
        rows=sorted((h for h in runner['history'] if h['surface']==raw['race']['surface']),key=lambda h:timestamp(h['occurred_at']),reverse=True)[:3]
        base=feature_output['horses'][horse]['base_ability']
        out[horse]={'agent':'N-VALUE-ABILITY-RECHECK','method':'best_recent3_vs_decay-v1',
                    'status':'AVAILABLE' if rows else 'UNAVAILABLE','history_rows':len(rows),
                    'recent_peak_score':max(h['performance_score'] for h in rows) if rows else None,
                    'gap_from_base':max(h['performance_score'] for h in rows)-base if rows else None,
                    'probability_override':False,
                    'note':'Correlated history is not added again to the main probability.'}
    return out

def nvalue_review(lock,candidates,odds_threshold):
    reviews=[]
    for candidate in candidates:
        if candidate['bet_type']!='WIN':continue
        horse=candidate['legs'][0];recheck=lock['ability_rechecks'][horse]
        price_edge=candidate['net_ev']>0 and candidate['decimal_odds']>=odds_threshold
        reviews.append({'horse_id':horse,'agent':'N-VALUE-POST-LOCK','prediction_hash':lock['lock_hash'],
                        'ability_recheck':recheck,'market_relative_value':candidate['relative_market_value'],
                        'net_ev':candidate['net_ev'],'price_edge':price_edge,
                        'decision':'REVIEW_CANDIDATE' if price_edge and recheck['status']=='AVAILABLE' else 'INSUFFICIENT_HISTORY' if price_edge else 'NO_PRICE_EDGE',
                        'automatic_adoption':False})
    return reviews
