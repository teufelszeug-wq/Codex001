"""Versioned structured-observation normalizer; experimental score mappings."""
from copy import deepcopy
from .contracts import digest,fields,numeric,validate

def clip(value):return min(100.,max(0.,value))

def normalize(observations):
    fields(observations,{'schema','mode','race','runners','bias','specialists','source'},
           {'schema','mode','race','runners','source'})
    if observations['schema']!='prism.engine.observations/v1':raise ValueError('observation schema rejected')
    if observations['source']['content_hash']!=digest({k:v for k,v in observations.items() if k!='source'}):raise ValueError('raw observation hash mismatch')
    raw=deepcopy(observations);raw['schema']='prism.engine.raw/v1'
    for runner in raw['runners']:
        converted=[]
        for h in runner['history']:
            fields(h,{'occurred_at','available_at','finish_position','starters','distance_m','surface','direction','class_rating','venue'},
                   {'occurred_at','available_at','finish_position','starters','distance_m','surface','direction','class_rating','venue'})
            n=h['starters'];rank=h['finish_position']
            if type(n) is not int or n<2 or type(rank) is not int or not 1<=rank<=n:raise ValueError('past rank observation rejected')
            row={k:v for k,v in h.items() if k not in {'finish_position','starters'}}
            row['performance_score']=100*(n-rank)/(n-1);converted.append(row)
        runner['history']=converted
        workout=runner.get('workout')
        if workout is not None:
            fields(workout,{'distance_m','time_s','reference_time_s','available_at'}, {'distance_m','time_s','reference_time_s','available_at'})
            numeric(workout['distance_m'],100,5000);time=numeric(workout['time_s'],1,1000);reference=numeric(workout['reference_time_s'],1,1000)
            runner['workout']={'score':clip(50+100*(reference-time)/reference),'available_at':workout['available_at']}
        body=runner.get('condition')
        if body is not None:
            fields(body,{'weight_kg','previous_weight_kg','assessment','available_at'}, {'weight_kg','previous_weight_kg','assessment','available_at'})
            weight=numeric(body['weight_kg'],100,2000);previous=numeric(body['previous_weight_kg'],100,2000);assessment=numeric(body['assessment'],0,100)
            runner['condition']={'score':clip(.75*assessment+.25*clip(100-500*abs(weight/previous-1))), 'available_at':body['available_at']}
        jockey=runner.get('jockey')
        if jockey is not None:
            fields(jockey,{'wins','rides','available_at'}, {'wins','rides','available_at'})
            rides=jockey['rides'];wins=jockey['wins']
            if type(rides) is not int or type(wins) is not int or not 0<=wins<=rides:raise ValueError('jockey observations rejected')
            runner['jockey']={'score':clip(50+100*((wins+1)/(rides+10)-.1)),'sample_size':rides,'available_at':jockey['available_at']}
    raw['source']['source_id']=raw['source']['source_id']+'|structured-normalizer-v1'
    raw['source']['content_hash']=digest({k:v for k,v in raw.items() if k!='source'})
    normalized=validate(raw)
    return normalized,{'normalizer':'structured-normalizer-v1-experimental','raw_hash':digest(observations),
                       'normalized_hash':digest(normalized),'source_authenticity_verified':False,
                       'mappings':['past ordinal percentile','workout relative-time proxy','body-weight/assessment proxy','jockey smoothed win-rate proxy'],
                       'note':'Reference times, assessment, and other signals require independent upstream evidence; mappings are not validated speed figures.'}
