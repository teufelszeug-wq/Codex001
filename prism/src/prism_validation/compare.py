"""Recompute matched-cohort metrics from immutable research predictions.

Public reports contain aggregates and hashes, never horse names or result rows.
Dead heats use equal fractional winner targets for multiclass LL and Brier.
"""
import hashlib
import json
import math
from itertools import combinations
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def indexed(rows):
    out = {}
    for row in rows:
        key = row['race_id']
        if key in out:
            raise ValueError('duplicate race ID')
        out[key] = row
    return out


def losses(probabilities, winners):
    if not probabilities or not winners or len(winners) != len(set(winners)):
        raise ValueError('invalid outcomes')
    if not set(winners) <= set(probabilities):
        raise ValueError('winner absent from prediction')
    if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
           for p in probabilities.values()) or abs(sum(probabilities.values())-1) > 1e-8:
        raise ValueError('invalid probability distribution')
    target = 1 / len(winners)
    ll = -sum(math.log(max(probabilities[w], 1e-15)) for w in winners)/len(winners)
    brier = sum((p-(target if k in winners else 0))**2 for k, p in probabilities.items())
    return ll, brier


def validate_row(row):
    losses(row['probabilities'], row['winners'])
    if row['stake_yen'] != 100 or type(row['stake_yen']) is not int:
        raise ValueError('research ticket must be fixed 100 yen')
    for k in ('refund_yen', 'payout_excluding_refund_yen'):
        if type(row[k]) is not int or row[k] < 0:
            raise ValueError('invalid settlement amount')
    if row['refund_yen'] not in (0, 100):
        raise ValueError('invalid refund')
    if row['refund_yen'] and row['payout_excluding_refund_yen']:
        raise ValueError('refund and payout overlap')


def load_archived(directory):
    directory = Path(directory)
    review_hashes = {}
    previous = '0'*64
    sequence = 0
    event_files = sorted(directory.glob('events_*.jsonl'))
    if not event_files:
        raise ValueError('archive event chain missing')
    for path in event_files:
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            event = json.loads(line)
            if (event['seq'] != sequence or event['previous_hash'] != previous or
                    event['hash'] != digest({k:v for k,v in event.items() if k!='hash'})):
                raise ValueError('archive event chain integrity mismatch')
            previous = event['hash']; sequence += 1
            if event['event'] == 'REVIEW_AND_LEARN':
                key = event['payload']['race_id']
                if key in review_hashes: raise ValueError('duplicate archived review event')
                review_hashes[key] = event['payload']['review_hash']
    rows = []
    for item in read(directory/'race_index.json'):
        pred = read(directory/'predictions'/item['file'])
        review = read(directory/'reviews'/item['file'])
        if pred['race_id'] != item['race_id'] or review['race_id'] != item['race_id']:
            raise ValueError('archive race binding mismatch')
        if pred['lock_hash'] != review['prediction_hash']:
            raise ValueError('archive prediction binding mismatch')
        if pred['lock_hash'] != digest({k:v for k,v in pred.items() if k!='lock_hash'}):
            raise ValueError('archive prediction content hash mismatch')
        if review_hashes.get(item['race_id']) != digest(review):
            raise ValueError('archive review content hash mismatch')
        tickets = pred['tickets']
        if len(tickets) != 1 or tickets[0]['type'] != 'WIN' or tickets[0]['stake_yen'] != 100:
            raise ValueError('expected one fixed-100 win ticket')
        if tickets[0]['number'] != review['pick']:
            raise ValueError('archive selection mismatch')
        # Legacy payout_yen INCLUDES refund: subtract once, never add twice.
        payout = review['payout_yen'] - review['refund_yen']
        row = {'race_id': item['race_id'], 'order_key': [review['date'], review['start'], item['race_id']],
               'probabilities': pred['probabilities']['win'], 'winners': review['winners'],
               'stake_yen': review['stake_yen'], 'payout_excluding_refund_yen': payout,
               'refund_yen': review['refund_yen'], 'prediction_hash': pred['lock_hash'],
               'pick': str(review['pick'])}
        validate_row(row)
        ll, brier = losses(row['probabilities'], row['winners'])
        if abs(ll-review['log_loss']) > 1e-9 or abs(brier-review['brier']) > 1e-9:
            raise ValueError('archive metric recomputation mismatch')
        if payout+row['refund_yen']-100 != review['profit_yen']:
            raise ValueError('archive profit mismatch')
        rows.append(row)
    indexed(rows)
    if set(review_hashes) != {r['race_id'] for r in rows}:
        raise ValueError('archive review event coverage mismatch')
    return rows


def load_b0(directory, reference_rows):
    directory = Path(directory)
    read_lines = lambda path: [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    predictions = indexed(read_lines(directory/'predictions.jsonl'))
    evaluations = indexed(read_lines(directory/'evaluations.jsonl'))
    if set(predictions) != set(evaluations):
        raise ValueError('B0 predictions/evaluations coverage differs')
    previous = '0'*64
    locked = set(); revealed = set(); updated = set()
    for event in read_lines(directory/'events.jsonl'):
        if (event['previous_hash'] != previous or
                event['hash'] != digest({k:v for k,v in event.items() if k!='hash'})):
            raise ValueError('B0 event chain integrity mismatch')
        previous = event['hash']; payload = event['payload']; key = payload['race_id']
        if key not in predictions:
            raise ValueError('B0 event unknown race')
        if event['event'] == 'PREDICTION_LOCK':
            if key in locked or payload['prediction_hash'] != predictions[key]['prediction_hash']:
                raise ValueError('B0 lock event mismatch')
            locked.add(key)
        elif event['event'] == 'RESULT_REVEAL':
            if key not in locked or key in revealed or payload['evaluation_hash'] != digest(evaluations[key]):
                raise ValueError('B0 evaluation content hash mismatch')
            revealed.add(key)
        elif event['event'] == 'HISTORY_UPDATE':
            if key not in revealed or key in updated:
                raise ValueError('B0 update chronology mismatch')
            updated.add(key)
        else:
            raise ValueError('B0 unknown event type')
    if locked != set(predictions) or revealed != locked or updated != locked:
        raise ValueError('B0 event coverage mismatch')
    reference = indexed(reference_rows)
    rows = []
    for key, pred in predictions.items():
        if key not in reference:
            raise ValueError('B0 outcome reference unavailable')
        evaluation = evaluations[key]
        if pred['prediction_hash'] != evaluation['prediction_hash']:
            raise ValueError('B0 prediction binding mismatch')
        if pred['prediction_hash'] != digest({k:v for k,v in pred.items() if k!='prediction_hash'}):
            raise ValueError('B0 prediction content hash mismatch')
        row = {'race_id': key, 'order_key': reference[key]['order_key'],
               'probabilities': pred['p_win'], 'winners': reference[key]['winners'],
               'stake_yen': evaluation['stake_yen'],
               'payout_excluding_refund_yen': evaluation['payout_excluding_refund_yen'],
               'refund_yen': evaluation['refund_yen'], 'prediction_hash': pred['prediction_hash'],
               'pick': str(pred['pick'])}
        validate_row(row)
        ll, brier = losses(row['probabilities'], row['winners'])
        if abs(ll-evaluation['log_loss']) > 1e-9 or abs(brier-evaluation['brier']) > 1e-9:
            raise ValueError('B0 metric recomputation mismatch')
        if row['payout_excluding_refund_yen']+row['refund_yen']-100 != evaluation['profit_yen']:
            raise ValueError('B0 profit mismatch')
        rows.append(row)
    return rows


def summarize(rows):
    if not rows:
        raise ValueError('no paired races')
    purchase = refund = payout = equity = peak = drawdown = 0
    ll_sum = brier_sum = 0.
    bins = [{'lower': i/10, 'upper': (i+1)/10, 'count': 0,
             'probability_sum': 0., 'target_sum': 0.} for i in range(10)]
    hits = 0
    for row in sorted(rows, key=lambda x: x['order_key']):
        validate_row(row)
        ll, brier = losses(row['probabilities'], row['winners'])
        ll_sum += ll
        brier_sum += brier
        purchase += row['stake_yen']; refund += row['refund_yen']; payout += row['payout_excluding_refund_yen']
        equity += row['payout_excluding_refund_yen']+row['refund_yen']-row['stake_yen']
        peak = max(peak, equity); drawdown = max(drawdown, peak-equity)
        hits += row['payout_excluding_refund_yen'] > 0
        for horse, p in row['probabilities'].items():
            bucket = bins[min(9, int(p*10))]
            bucket['count'] += 1; bucket['probability_sum'] += p
            bucket['target_sum'] += 1/len(row['winners']) if horse in row['winners'] else 0
    ece = 0.; count = sum(b['count'] for b in bins)
    for bucket in bins:
        n = bucket['count']
        bucket['mean_probability'] = bucket.pop('probability_sum')/n if n else None
        bucket['observed_fractional_win_rate'] = bucket.pop('target_sum')/n if n else None
        if n:
            ece += n/count*abs(bucket['mean_probability']-bucket['observed_fractional_win_rate'])
    effective = purchase-refund
    return {'races': len(rows), 'log_loss': ll_sum/len(rows), 'brier': brier_sum/len(rows),
            'gross_stake_yen': purchase, 'refund_yen': refund, 'effective_stake_yen': effective,
            'payout_excluding_refund_yen': payout, 'profit_yen': payout-effective,
            'effective_return_rate': payout/effective if effective else None,
            'gross_return_rate_including_refund': (payout+refund)/purchase,
            'max_drawdown_yen': drawdown, 'winning_tickets': hits,
            'calibration': {'method': 'pooled-runner-equal-width-10-fractional-deadheat', 'runner_count': count,
                            'ece': ece, 'bins': bins},
            'rows_hash': digest(sorted(rows, key=lambda x:x['race_id']))}


def compare_runs(runs, scope='SYNTHETIC_COMPARISON'):
    if len(runs) < 2:
        raise ValueError('at least two research runs required')
    tables = {name: indexed(rows) for name, rows in sorted(runs.items())}
    paired = set.intersection(*(set(rows) for rows in tables.values()))
    if not paired:
        raise ValueError('no common cohort')
    for key in paired:
        group = [rows[key] for rows in tables.values()]
        if any(set(r['probabilities']) != set(group[0]['probabilities']) or
               set(r['winners']) != set(group[0]['winners']) or
               r['order_key'] != group[0]['order_key'] for r in group[1:]):
            raise ValueError('paired runner/outcome/order mismatch')
    metrics = {name: summarize([rows[k] for k in sorted(paired)]) for name, rows in tables.items()}
    deltas = []
    for a, b in combinations(tables, 2):
        diffs = {metric: [] for metric in ('log_loss', 'brier')}
        changed = 0
        for key in sorted(paired):
            ra, rb = tables[a][key], tables[b][key]
            la, lb = losses(ra['probabilities'], ra['winners']), losses(rb['probabilities'], rb['winners'])
            for i, metric in enumerate(diffs): diffs[metric].append(lb[i]-la[i])
            changed += ra.get('pick') != rb.get('pick')
        deltas.append({'from': a, 'to': b, 'races': len(paired), 'changed_picks': changed,
                       'mean_paired_delta_to_minus_from': {k:sum(v)/len(v) for k,v in diffs.items()},
                       'profit_delta_yen': metrics[b]['profit_yen']-metrics[a]['profit_yen'],
                       'interpretation': 'Descriptive matched-cohort differences, not causal or prospective superiority.'})
    report = {'schema': 'prism.validation.comparison/v1', 'scope': scope,
              'coverage': {'paired_races': len(paired), 'paired_race_ids_hash': digest(sorted(paired)),
                           'available_by_run': {k:len(v) for k,v in tables.items()},
                           'excluded_noncommon_by_run': {k:len(set(v)-paired) for k,v in tables.items()}},
              'runs': metrics, 'paired_comparisons': deltas,
              'strict_pit_certified_races': 0, 'february_verified': False,
              'phase_d_complete': False, 'full_phase_b_real_data_validated': False,
              'definitions': {'log_loss': 'mean over races of mean negative log winner probability; floor 1e-15',
                              'brier': 'mean over races of sum over runners of squared error; dead-heat targets sum to 1',
                              'effective_return_rate': 'payout excluding refunds / (purchase minus refunds)',
                              'drawdown': 'maximum peak-to-trough cumulative net profit, starting at zero; same timestamp lexical race ID order',
                              'calibration': 'descriptive pooled-runner bins, not fitted calibration or held-out certification'},
              'limitations': ['Retrospective archived research; strict point-in-time certification remains absent.',
                              'No February evaluation and no full-feature new Phase B real-race performance validation.',
                              'Outcome consistency is cross-checked against archived reviews, not independently recertified official sources.']}
    report['report_hash'] = digest(report)
    return report
