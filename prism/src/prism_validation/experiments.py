"""Retrospective probability-only ablations and dated train/holdout calibration."""
from copy import deepcopy
from math import exp, log
from pathlib import Path
from .compare import read, indexed, digest, losses, summarize


def probability_metrics(rows):
    metrics = summarize(rows)
    return {k:metrics[k] for k in ('races', 'log_loss', 'brier', 'calibration')}


def archived_experts(directory, reference_rows):
    directory = Path(directory); reference = indexed(reference_rows)
    expert_rows = {}
    for item in read(directory/'race_index.json'):
        pred = read(directory/'predictions'/item['file'])
        if pred['race_id'] != item['race_id'] or item['race_id'] not in reference:
            raise ValueError('expert prediction race binding mismatch')
        if (pred['lock_hash'] != digest({k:v for k,v in pred.items() if k!='lock_hash'}) or
                pred['lock_hash'] != reference[item['race_id']]['prediction_hash']):
            raise ValueError('expert prediction content hash mismatch')
        for name, probabilities in pred['experts'].items():
            if set(probabilities) != set(reference[item['race_id']]['probabilities']):
                raise ValueError('expert coverage mismatch')
            row = deepcopy(reference[item['race_id']]); row['probabilities'] = probabilities
            expert_rows.setdefault(name, []).append(row)
    if any(len(rows) != len(reference) for rows in expert_rows.values()):
        raise ValueError('expert race coverage mismatch')
    report = {'schema': 'prism.validation.experts/v1', 'scope': 'ARCHIVED_PROBABILITY_ONLY',
              'paired_races': len(reference),
              'experts': {k:probability_metrics(v) for k,v in sorted(expert_rows.items())},
              'input_hash': digest({k:[{'race_id':r['race_id'],'probabilities':r['probabilities'],'winners':r['winners']}
                                     for r in sorted(v,key=lambda r:r['race_id'])] for k,v in sorted(expert_rows.items())}),
              'ticket_repriced': False, 'profitability_comparison_available': False,
              'strict_pit_certified_races': 0,
              'note': 'Same archived races and runner coverage; experts share inputs and learned mixture history. This is not controlled causal feature attribution. No expert ticket payouts were inferred.'}
    report['report_hash'] = digest(report)
    return report


def transform(probabilities, temperature):
    scores = {k:log(max(p,1e-15))/temperature for k,p in probabilities.items()}
    maximum = max(scores.values()); values = {k:exp(v-maximum) for k,v in scores.items()}
    total = sum(values.values())
    return {k:v/total for k,v in values.items()}


def chronological_calibration(rows, train_end='20260115', holdout_end='20260131',
                              grid=(.5,.75,1.,1.25,1.5,2.,3.)):
    """Select on train only, report untouched later dates; freeze without refit.

    This split was specified during retrospective analysis, not preregistered in January.
    The artifact is a research candidate and must not be mistaken for PIT provenance.
    """
    indexed(rows)
    if not grid or any(type(t) not in (int,float) or not .1 <= t <= 10 for t in grid):
        raise ValueError('calibration grid rejected')
    train = [r for r in rows if '20260101' <= r['order_key'][0] <= train_end]
    holdout = [r for r in rows if train_end < r['order_key'][0] <= holdout_end]
    if not train or not holdout or len(train)+len(holdout) != len(rows):
        raise ValueError('nonempty exhaustive chronological split required')
    if max(r['order_key'][0] for r in train) >= min(r['order_key'][0] for r in holdout):
        raise ValueError('chronological overlap')
    for row in rows: losses(row['probabilities'], row['winners'])
    search = [{'temperature':t, 'train_log_loss':sum(losses(transform(r['probabilities'],t),r['winners'])[0]
                                                   for r in train)/len(train)} for t in grid]
    selected = min(search, key=lambda x:(x['train_log_loss'],x['temperature']))['temperature']
    adjusted = [dict(r, probabilities=transform(r['probabilities'],selected)) for r in holdout]
    artifact = {'schema':'prism.validation.frozen-calibration/v1', 'base_model':'B0-ordinal-ability-research-1',
                'method':'temperature-only-fixed-grid', 'temperature':selected,
                'training_dates':['20260101',train_end], 'training_races':len(train),
                'training_data_hash':digest(sorted(train,key=lambda r:r['race_id'])),
                'grid':list(grid), 'freeze_scope':'PROPOSED_FEBRUARY_RESEARCH_RULE',
                'refitted_on_holdout':False, 'february_used':False,
                'strict_pit_certified':False, 'pre_registered_in_january':False,
                'production_adopted':False}
    artifact['artifact_hash']=digest(artifact)
    report = {'schema':'prism.validation.chronological-calibration/v1', 'scope':'RETROSPECTIVE_JANUARY_SPLIT',
              'training_races':len(train), 'holdout_races':len(holdout),
              'training_dates':['20260101',train_end], 'holdout_dates':[min(r['order_key'][0] for r in holdout),holdout_end],
              'search_train_only':search, 'selected_temperature':selected,
              'holdout_before':probability_metrics(holdout), 'holdout_after':probability_metrics(adjusted),
              'holdout_hash':digest(sorted(holdout,key=lambda r:r['race_id'])),
              'frozen_artifact':artifact, 'bet_policy_changed':False, 'ticket_repriced':False,
              'strict_pit_certified_races':0, 'february_verified':False,
              'note':'Grid selection uses January 1–15 only; January 16–31 is evaluation only. This retrospective experiment is not prospective evidence. The frozen candidate has not been applied to February or production.'}
    report['report_hash']=digest(report)
    return report
