"""Phase B engineering pipeline, experimental and explicitly not production."""
from copy import deepcopy
from math import log,sqrt
from .contracts import digest,fields,numeric,timestamp,validate
from .features import features
from .probability import softmax,distribution,marginals,simulate_joint,scenario_joint,apply_calibration
from .market import value_candidates,optimize
from .specialists import ability_recheck,nvalue_review

DEFAULT_CONFIG={'half_life_days':180.,'cold_start_prior':50.,'score_temperature':18.,
                'runs':10000,'seed':42,'budget_yen':500,'max_points':5,'min_net_ev':.0,
                'max_quote_age_seconds':300,'candidate_pool_limit':20,'max_exposure_per_leg':3,
                'longshot_odds_min':10.}
MODULES=('base_ability','course_surface_class','state_recency_rotation','pace','bias_tbi_ssi',
         'workout','condition','sectional','jockey','specialist','surface_specific')

def configuration(config):
    fields(config,DEFAULT_CONFIG,set(DEFAULT_CONFIG))
    c=deepcopy(config)
    numeric(c['half_life_days'],.01,1000);numeric(c['score_temperature'],1,1000)
    numeric(c['cold_start_prior'],0,100);numeric(c['min_net_ev'],0,1000)
    numeric(c['max_quote_age_seconds'],0,86400);numeric(c['longshot_odds_min'],1,100000)
    for name,low,high in [('runs',1,1000000),('seed',0,2**63),('budget_yen',0,100000),
                          ('max_points',0,6),('candidate_pool_limit',1,24),('max_exposure_per_leg',1,100)]:
        if type(c[name]) is not int or not low<=c[name]<=high:raise ValueError('config integer range rejected')
    if c['budget_yen']%100:raise ValueError('budget not fixed units')
    return c

def predict(raw,locked_at,config=None,calibration=None,disabled_modules=()):
    data=validate(raw);cfg=configuration(DEFAULT_CONFIG if config is None else config)
    locked=timestamp(locked_at);cutoff=timestamp(data['race']['cutoff'])
    if locked>cutoff:raise ValueError('prediction locked after cutoff')
    if data['source']['available_at'] is not None and timestamp(data['source']['available_at'])>locked:raise ValueError('source unavailable at lock')
    # Every individual feature used must also predate the lock, not merely start time.
    def check_times(obj):
        if isinstance(obj,dict):
            if obj.get('occurred_at') is not None and timestamp(obj['occurred_at'])>=locked:raise ValueError('history occurred after lock')
            if obj.get('available_at') is not None and timestamp(obj['available_at'])>locked:raise ValueError('feature unavailable at lock')
            for value in obj.values():check_times(value)
        elif isinstance(obj,list):
            for value in obj:check_times(value)
    check_times(data)
    disabled=set(disabled_modules)
    if disabled-set(MODULES):raise ValueError('unknown ablation module')
    fit=features(data,cfg);scores={};coverage={}
    for horse,f in fit['horses'].items():
        score=cfg['cold_start_prior'] if 'base_ability' in disabled else f['base_ability']
        for name,value in f['components'].items():
            if name not in disabled and value is not None:score+=value
        scores[horse]=score;coverage[horse]={k:('DISABLED' if k in disabled else v) for k,v in f['availability'].items()}
    pace=fit['pace_distribution']
    scenarios={}
    if pace is not None and 'pace' not in disabled:
        for label in pace:
            adjusted={h:scores[h]-fit['horses'][h]['components']['pace']+fit['horses'][h]['pace_scenarios'][label] for h in scores}
            scenarios[label]=softmax(adjusted,cfg['score_temperature'])
    else:pace={'NO_PACE_MODEL':1.};scenarios={'NO_PACE_MODEL':softmax(scores,cfg['score_temperature'])}
    pre={h:sum(pace[label]*p[h] for label,p in scenarios.items()) for h in scores}
    win,cal_status=apply_calibration(pre,calibration,data['race']['race_id'],locked_at)
    ranks=scenario_joint(scenarios,pace,win,pre);probabilities=marginals(win,ranks);mc=simulate_joint(ranks,cfg['runs'],cfg['seed'])
    artifact={'schema':'prism.engine.prediction/v1','race_id':data['race']['race_id'],'cutoff':data['race']['cutoff'],
              'locked_at':locked_at,'mode':data['mode'],'input_hash':digest(data),'config_hash':digest(cfg),
              'calibration_hash':None if calibration is None else calibration['artifact_hash'],
              'calibration_status':cal_status,'disabled_modules':sorted(disabled),'scores':scores,
              'features':fit,'coverage':coverage,'win':win,'probabilities':probabilities,'rank_distribution':ranks,
              'frames':{r['horse_id']:str(r['frame_no']) for r in data['runners']},
              'monte_carlo':mc,'model_version':'prism-core-engine-0.1-experimental',
              'rank_model':'CALIBRATED_PACE_MIXTURE_PL_NOT_PHYSICAL_RACE_SIMULATION',
              'scenario_win_uncalibrated':scenarios,
              'ability_rechecks':ability_recheck(data,fit),
              'performance_validated':False,'source_authenticity_verified':False}
    artifact['uncertainty']={'normalized_entropy':-sum(p*log(p) for p in win.values() if p)/log(len(win)),
                             'mc_standard_errors':{k:sqrt(p*(1-p)/cfg['runs']) for k,p in win.items()},
                             'missing_feature_count':sum(len(h['missing']) for h in fit['horses'].values()),
                             'note':'Entropy and MC sampling error are not predictive confidence intervals.'}
    artifact['lock_hash']=digest(artifact)
    return artifact

def post_market(lock,market,config=None):
    cfg=configuration(DEFAULT_CONFIG if config is None else config)
    if digest(cfg)!=lock['config_hash']:raise ValueError('config changed after lock')
    candidates=value_candidates(lock,market,cfg);plan=optimize(candidates,cfg)
    plan['race_id']=lock['race_id'];plan['prediction_hash']=lock['lock_hash'];plan['plan_hash']=digest(plan)
    return {'race_id':lock['race_id'],'prediction_hash':lock['lock_hash'],'market_hash':digest(market),
            'candidate_values':candidates,'nvalue_reviews':nvalue_review(lock,candidates,cfg['longshot_odds_min']),
            'plan':plan,'execution_allowed':False,'mode':lock['mode'],
            'note':'Research candidates only; no betting execution or profitability claim.'}
