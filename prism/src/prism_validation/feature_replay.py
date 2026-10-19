"""Dated, day-embargo feature experiments using reconstructed observations.

Outcome objects remain in this evaluator; the feature model only receives a
whitelisted row. All feature sources lack certified historical publication time.
"""
import json
import math
import random
import sqlite3
from collections import defaultdict
from datetime import datetime
from itertools import groupby
from pathlib import Path

from .compare import digest, losses, summarize

FEATURES = ('jockey_signal', 'body_change', 'body_weight')
EXCLUDED_STATUSES = ('取消', '除外', '取止', '競走除外')


def load_observations(database):
    """Read-only join keyed by race and runner number; reject ambiguous sources."""
    con = sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)
    try:
        rows = con.execute('SELECT o.race_id,e.horse_no,e.jockey_id,o.payload_json,o.content_hash '
                           'FROM observations o JOIN entries e ON o.race_id=e.race_id '
                           'AND o.horse_id=e.horse_id')
        out = {}
        for race, number, jockey, payload, content_hash in rows:
            payload = json.loads(payload)
            if payload.get('schema') != 'prism.recovered-observations-hold/v1':
                continue
            key = (race, str(number))
            if key in out:
                raise ValueError('duplicate reconstructed observation')
            values = payload['observations']
            out[key] = {'jockey_id':jockey,
                        'body_weight': values.get('body_weight_kg'),
                        'body_change': values.get('body_weight_change_kg'),
                        'source_hash':content_hash}
        return out
    finally:
        con.close()


def _updates(race):
    started = [r for r in race['results'] if r['status'] not in EXCLUDED_STATUSES]
    ranks = {r['number']:r['rank'] for r in started if r['rank'] is not None}
    n = len(started)
    if n < 2:
        return []
    return [(h['identity'], {'date':race['date'], 'surface':race['surface'],
                            'score':100*(n-ranks[h['number']])/(n-1)})
            for h in race['entrants'] if h['number'] in ranks and 1 <= ranks[h['number']] <= n]


def _baseline(race, history):
    target = datetime.strptime(race['date'], '%Y%m%d')
    scores = {}
    for horse in race['entrants']:
        values = history[horse['identity']]
        weighted = mass = 0.
        for past in values:
            if past['date'] >= race['date']:
                raise ValueError('same-day outcome leakage')
            if past['surface'] != race['surface']:
                continue
            days = (target-datetime.strptime(past['date'], '%Y%m%d')).days
            weight = .5**(days/180)
            weighted += past['score']*weight
            mass += weight
        scores[str(horse['number'])] = weighted/mass if mass else 50.
    maximum = max(scores.values())
    values = {k:math.exp((v-maximum)/18.) for k,v in scores.items()}
    total = sum(values.values())
    return {k:v/total for k,v in values.items()}


def build_rows(january, bootstrap, observations):
    if any(r['date'] >= '20260101' for r in bootstrap):
        raise ValueError('bootstrap includes January')
    if len({r['race_id'] for r in january}) != len(january):
        raise ValueError('duplicate races')
    history = defaultdict(list)
    for race in sorted(bootstrap,key=lambda r:(r['date'],r['start'],r['race_id'])):
        for horse, update in _updates(race):
            history[horse].append(update)
    jockey_history = defaultdict(lambda:[0.,0])
    global_wins = global_starts = 0.
    output = []
    for date, group in groupby(sorted(january,key=lambda r:(r['date'],r['start'],r['race_id'])),lambda r:r['date']):
        day = list(group)
        # Freeze every prediction for this day before incorporating any result.
        for race in day:
            probabilities = _baseline(race, history)
            features = {}; source_hashes = []
            prior = global_wins/global_starts if global_starts else .1
            for horse in race['entrants']:
                number = str(horse['number']); obs = observations.get((race['race_id'],number),{})
                jid = obs.get('jockey_id'); wins, starts = jockey_history[jid] if jid else (0.,0)
                weight = obs.get('body_weight'); change = obs.get('body_change')
                features[number] = {'jockey_signal':(wins+20*prior)/(starts+20)-prior if starts else None,
                                    'body_weight':(weight-450)/100 if weight is not None else None,
                                    'body_change':change/10 if change is not None else None}
                if obs.get('source_hash'):source_hashes.append(obs['source_hash'])
            output.append({'race_id':race['race_id'],'date':date,
                           'baseline_probabilities':probabilities,'features':features,
                           'winner_ids':[str(r['number']) for r in race['results'] if r['rank']==1],
                           'source_observation_hash':digest(sorted(source_hashes)),
                           'source_time_verified':False})
        for race in day:
            for horse, update in _updates(race): history[horse].append(update)
            started = [r for r in race['results'] if r['status'] not in EXCLUDED_STATUSES]
            winners = [r for r in started if r['rank']==1]
            for result in started:
                obs = observations.get((race['race_id'],str(result['number'])),{})
                jid = obs.get('jockey_id'); win = (1/len(winners) if result['rank']==1 else 0.) if winners else 0.
                if jid:
                    jockey_history[jid][0] += win; jockey_history[jid][1] += 1
                global_wins += win; global_starts += 1
    return output


def model_input(row, include_outcomes=False):
    fields = ('race_id','date','baseline_probabilities','features')
    out = {k:row[k] for k in fields}
    if include_outcomes: out['winner_ids'] = row['winner_ids']
    return out


def research_paper_dto(race, row, model, database):
    """Local research paper handoff; contains licensed-source names, not for Git."""
    from prism_research_models import predict_model
    if race['race_id'] != row['race_id']:
        raise ValueError('paper race binding mismatch')
    prediction = predict_model(model,model_input(row))
    con = sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        entries = {number:(horse,frame) for number,horse,frame in con.execute(
            'SELECT horse_no,horse_id,frame_no FROM entries WHERE race_id=?',(race['race_id'],))}
    finally:con.close()
    runners=[]
    for h in sorted(race['entrants'],key=lambda h:h['number']):
        entity, frame = entries[h['number']]
        runners.append({'horse_id':entity,'horse_no':h['number'],'frame_no':frame,
                        'name':h['name'],'p_win':prediction['probabilities'][str(h['number'])]})
    dto = {'schema':'prism.paper.research-race/v1',
            'race_id':race['race_id'],'date':race['date'],'start':race['start'],
            'venue':race['venue'],'title':race['title'],'distance_m':race['distance'],
            'surface':race['surface'],'direction':race['direction'],'runners':runners,
            'mode':'HISTORICAL_RECONSTRUCTION_NOT_PIT','strict_pit_certified':False,
            'input_hash':prediction['input_hash'],'prediction_hash':digest(prediction),
            'model_hash':prediction['model_hash'],
            'source_refs':[race['source_kind'],row['source_observation_hash']],
            'discussions':[], 'training_achievement_verified':False,
            'note':'January held-out research prediction; source publication time unknown; no dialogue invented.'}
    dto['dto_hash'] = digest(dto)
    return dto


def settle(probabilities, race):
    """Only a documented winner payout or a known losing ticket becomes zero."""
    winners = [str(r['number']) for r in race['results'] if r['rank']==1]
    losses(probabilities, winners)
    pick = min(probabilities,key=lambda k:(-probabilities[k],int(k)))
    result = next((r for r in race['results'] if str(r['number'])==pick),None)
    if result is None: raise ValueError('selection result missing')
    refund = 100 if result['status'] in EXCLUDED_STATUSES else 0
    if not refund and pick in winners and pick not in race['win_payouts']:
        raise ValueError('winning payout unavailable')
    payout = race['win_payouts'][pick] if not refund and pick in winners else 0
    return {'race_id':race['race_id'],'order_key':[race['date'],race['start'],race['race_id']],
            'probabilities':probabilities,'winners':winners,'pick':pick,'stake_yen':100,
            'payout_excluding_refund_yen':payout,'refund_yen':refund,
            'prediction_hash':digest(probabilities)}


def bootstrap_deltas(base, candidate, repeats=1000, seed=20261019):
    """Paired day-block intervals conditional on this fixed fitted model."""
    blocks = defaultdict(list)
    for a,b in zip(base,candidate):
        if a['race_id'] != b['race_id']:raise ValueError('unpaired bootstrap')
        la,lb = losses(a['probabilities'],a['winners']),losses(b['probabilities'],b['winners'])
        blocks[a['order_key'][0]].append((lb[0]-la[0],lb[1]-la[1],
            b['payout_excluding_refund_yen']+b['refund_yen']-a['payout_excluding_refund_yen']-a['refund_yen']))
    days = sorted(blocks); rng = random.Random(seed); samples = [[],[],[]]
    for _ in range(repeats):
        rows = [row for day in rng.choices(days,k=len(days)) for row in blocks[day]]
        for i in range(3):samples[i].append(sum(r[i] for r in rows)/len(rows))
    return {'method':'paired-day-block-percentile-conditional-on-frozen-model','blocks':len(days),
            'repeats':repeats,'seed':seed,'interval_95':{
                metric:[sorted(values)[int(.025*(repeats-1))],sorted(values)[int(.975*(repeats-1))]]
                for metric,values in zip(('log_loss_delta','brier_delta','profit_delta_per_race_yen'),samples)}}


def run_experiment(january, bootstrap, observations):
    from prism_research_models import fit_model, predict_model
    rows = build_rows(january,bootstrap,observations)
    train = [r for r in rows if r['date'] <= '20260115']
    holdout = [r for r in rows if r['date'] > '20260115']
    if not train or not holdout:raise ValueError('empty dated split')
    races = {r['race_id']:r for r in january}
    variants = {'ability_only':(), 'plus_jockey':('jockey_signal',),
                'plus_body':('body_change','body_weight'), 'plus_both':FEATURES}
    models = {}; evaluated = {}; missing = {}
    for name, names in variants.items():
        model = fit_model([model_input(r,True) for r in train],names,
                          training_cutoff='2026-01-15T23:59:59+09:00')
        models[name] = model
        evaluated[name] = [settle(predict_model(model,model_input(r))['probabilities'],races[r['race_id']]) for r in holdout]
        total = sum(len(r['features']) for r in holdout)
        missing[name] = {f:sum(x[f] is None for r in holdout for x in r['features'].values())/total for f in names}
    public_models = {k:{**{f:v for f,v in m.items() if f!='train_race_ids'},
                        'train_race_ids_hash':digest(m['train_race_ids']),
                        'train_race_count':len(m['train_race_ids']),
                        'summary_only':True} for k,m in models.items()}
    report = {'schema':'prism.validation.feature-experiment/v1','scope':'RETROSPECTIVE_JANUARY_RECONSTRUCTION',
              'training_races':len(train),'holdout_races':len(holdout),
              'training_dates':['20260101','20260115'],'holdout_dates':['20260116','20260131'],
              'cohort_hash':digest([r['race_id'] for r in holdout]),'input_hash':digest(rows),
              'baseline':'B0 ordinal ability rebuilt with prior-day-only history; Dec bootstrap; half-life180 temperature18 cold50',
              'feature_policy':'jockey earlier-day January results only; wins fractional for dead heats; 20-start shrinkage; body weight/change reconstructed raw; missing mask retained',
              'excluded_features':['jockey_counts_unverified','current_results','popularity','last_3f','career_snapshot'],
              'models':public_models,'runs':{k:summarize(v) for k,v in evaluated.items()},'missing_rates':missing,
              'paired_uncertainty':{k:bootstrap_deltas(evaluated['ability_only'],v) for k,v in evaluated.items() if k!='ability_only'},
              'strict_pit_certified_races':0,'february_verified':False,'production_adopted':False,
              'phase_d_complete':False,'limitations':['Historical publication timestamps unknown; reconstructed pre observations are not certified PRE.',
              'Jockey identities provisional; December jockey histories unavailable; explicit initial prior.',
              'Holdout updates history only after each full day; coefficients remain frozen.',
              'This retrospective split was not preregistered in January. Conditional intervals do not refit training models.',
              'Simple additional features do not establish full specialist, N-Value, workout, or condition models.']}
    report['report_hash'] = digest(report)
    return report, rows, models
