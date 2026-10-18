"""Synthetic acceptance fixture; not a real race, transcript or training record."""
from copy import deepcopy
from prism_engine.contracts import digest
from prism_engine.probability import fit_calibration

def seal(raw):
    raw['source']['content_hash']=digest({k:v for k,v in raw.items() if k!='source'})
    return raw

def raw_fixture(surface='DIRT'):
    runners=[]
    for i in range(1,7):
        available='2026-01-01T09:00:00+09:00'
        runners.append({'horse_id':f'h{i}','horse_no':i,'frame_no':1 if i<3 else i-1,'barrier_no':i,'carried_weight':55,
                        'history':[{'occurred_at':'2025-12-01T10:00:00+09:00','available_at':'2025-12-01T11:00:00+09:00',
                                    'performance_score':85-8*i,'distance_m':1600,'surface':surface,'direction':'LEFT','class_rating':50,'venue':'TEST'}],
                        'state':{'readiness':65-i,'rotation_days':28,'available_at':available},
                        'style':{'escape':.2,'front':.3,'mid':.3,'closer':.2,'early_speed':70-i,'resistance':60+i,'available_at':available},
                        'workout':{'score':70-i,'available_at':available},'condition':{'score':60+i,'available_at':available},
                        'jockey':{'score':60+i,'sample_size':100,'available_at':available},
                        'sectional':{'score':65-i,'available_at':available},'path_position':(i-3)/3,
                        'ban_ei':{'barrier_skill':70-i,'pulling_power':70-i,'available_at':available},
                        'jump':{'jump_skill':70-i,'available_at':available}})
    raw={'schema':'prism.engine.raw/v1','mode':'SYNTHETIC',
         'race':{'race_id':'TEST|20260101|X|1','venue':'TEST','surface':surface,'distance_m':1600,
                 'direction':'LEFT','class_rating':50,'cutoff':'2026-01-01T10:00:00+09:00','barrier_count':6},
         'runners':runners,'bias':{'gate':.2,'path':.1,'front':.2,'ssi':.1,'positive_lane':'OUTER',
                                 'water_content':30,'available_at':'2026-01-01T09:00:00+09:00'},
         'specialists':[{'horse_id':f'h{i}','agent_id':'ABILITY-REVIEW','evidence_id':f'synthetic-e{i}','delta':2-i/6,'confidence':.8,'available_at':'2026-01-01T09:00:00+09:00'} for i in range(1,7)],
         'source':{'source_id':'SYNTHETIC_ONLY','available_at':'2026-01-01T09:00:00+09:00','content_hash':''}}
    return seal(raw)

def calibration_fixture():
    rows=[{'race_id':f'TRAIN{i}','outcome_available_at':'2025-12-15T10:00:00+09:00',
           'probabilities':{'h1':.6,'h2':.4},'winners':['h1' if i<3 else 'h2']} for i in range(5)]
    return fit_calibration(rows,'2025-12-31T23:59:00+09:00',[.75,1.,1.25,1.5])

def observations_fixture():
    raw=raw_fixture();raw['schema']='prism.engine.observations/v1'
    for i,r in enumerate(raw['runners']):
        for h in r['history']:
            del h['performance_score'];h['finish_position']=i+1;h['starters']=10
        r['workout']={'distance_m':800,'time_s':50+i,'reference_time_s':55,'available_at':r['workout']['available_at']}
        r['condition']={'weight_kg':480+i,'previous_weight_kg':480,'assessment':65,'available_at':r['condition']['available_at']}
        r['jockey']={'wins':15-i,'rides':100,'available_at':r['jockey']['available_at']}
    return seal(raw)

def market_fixture(lock):
    quotes=[{'bet_type':'WIN','legs':[f'h{i}'],'odds_low':3+2*i,'odds_high':3+2*i} for i in range(1,7)]
    for kind,legs in [('PLACE',['h1']),('QUINELLA',['h1','h2']),('EXACTA',['h1','h2']),('WIDE',['h1','h2']),
                      ('TRIO',['h1','h2','h3']),('TRIFECTA',['h1','h2','h3']),('FRAME',['1','1'])]:
        quotes.append({'bet_type':kind,'legs':legs,'odds_low':20,'odds_high':25})
    return {'race_id':lock['race_id'],'prediction_hash':lock['lock_hash'],'observed_at':'2026-01-01T09:56:00+09:00',
            'opened_at':'2026-01-01T09:57:00+09:00','quotes':quotes,'place_slots':2}
