"""Content-addressed A–E handoff; integrity checks are not source certification.

Artifacts use ``{kind: {'stage': 'PRE'|'POST', 'payload': JSON value,
'depends_on': [kind, ...]}}``. Dependencies are optional. PRE payloads reject
known result-bearing structural keys; prose truth and source authenticity still
require review. No bet execution, learning achievement, or PIT certification is
granted by these APIs.
"""
from copy import deepcopy
from pathlib import Path
import json
from math import isfinite, isclose
import re

from prism_engine.contracts import MODES, digest, timestamp, validate, numeric
from prism_engine.market import ticket_key, UNORDERED

SCHEMA = 'prism.exchange.manifest/v1'
_HASH = re.compile(r'^[0-9a-f]{64}$')
_KIND = re.compile(r'^[a-z][a-z0-9_.-]{0,79}$')
_BINDINGS = ('race_id', 'input_hash', 'prediction_hash', 'mode')
_POST_KEYS = frozenset({
    'result', 'results', 'official_result', 'settlement', 'winners',
    'finishing_order', 'outcome', 'payouts', 'payout_yen', 'refund_yen',
    'profit_yen', 'realized_roi', 'result_revealed',
})


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _hash(value, name):
    _require(isinstance(value, str) and _HASH.fullmatch(value), name + ' must be SHA256')


def _identity(bundle):
    _require(isinstance(bundle, dict), 'bundle must be an object')
    _require(set(bundle) <= {'schema', 'prediction', 'market_values', 'raw', 'racecard',
                            'normalization', 'training_achievement_verified', 'production_deployed',
                            'settlement', 'learning_review'}, 'unknown bundle fields rejected')
    _require(bundle.get('schema') == 'prism.engine.bundle/v1', 'engine bundle schema rejected')
    prediction = bundle.get('prediction')
    _require(isinstance(prediction, dict), 'prediction required')
    for key in ('race_id', 'input_hash', 'lock_hash', 'mode', 'cutoff', 'locked_at'):
        _require(key in prediction, 'missing prediction ' + key)
    _require(isinstance(prediction['race_id'], str) and prediction['race_id'], 'race identity required')
    _require(prediction['mode'] in MODES, 'prediction mode rejected')
    _hash(prediction['input_hash'], 'input hash')
    _hash(prediction['lock_hash'], 'prediction hash')
    _require(prediction['lock_hash'] == digest({k: v for k, v in prediction.items() if k != 'lock_hash'}),
             'prediction lock changed')
    _require(timestamp(prediction['locked_at']) <= timestamp(prediction['cutoff']),
             'prediction locked after cutoff')
    identity = {'race_id': prediction['race_id'], 'input_hash': prediction['input_hash'],
                'prediction_hash': prediction['lock_hash'], 'mode': prediction['mode']}
    market = bundle.get('market_values')
    _require(isinstance(market, dict), 'market values required')
    for key in ('race_id', 'prediction_hash', 'mode'):
        _require(market.get(key) == identity[key], 'market ' + key + ' mismatch')
    _require(market.get('execution_allowed') is False, 'execution permission rejected')
    plan = market.get('plan')
    _require(isinstance(plan, dict), 'plan required')
    for key in ('race_id', 'prediction_hash'):
        _require(plan.get(key) == identity[key], 'plan ' + key + ' mismatch')
    _require(plan.get('plan_hash') == digest({k: v for k, v in plan.items() if k != 'plan_hash'}),
             'plan hash mismatch')
    _plan(plan, market.get('candidate_values'), prediction)
    feature_horses = prediction.get('features', {}).get('horses')
    _require(isinstance(feature_horses, dict) and set(feature_horses) == set(prediction.get('win', {}))
             and set(feature_horses) == set(prediction.get('frames', {})), 'prediction feature roster mismatch')
    horse_numbers, barrier_numbers = set(), set()
    for horse, feature in feature_horses.items():
        _require(isinstance(feature, dict), 'prediction horse feature required')
        for key, high in (('horse_no', 24), ('frame_no', 8), ('barrier_no', 24)):
            _require(type(feature.get(key)) is int and 1 <= feature[key] <= high,
                     'prediction numbering rejected: ' + key)
        _require(feature['horse_no'] not in horse_numbers and feature['barrier_no'] not in barrier_numbers,
                 'prediction numbering duplicate')
        horse_numbers.add(feature['horse_no']); barrier_numbers.add(feature['barrier_no'])
        _require(prediction['frames'][horse] == str(feature['frame_no']), 'prediction frame binding mismatch')
    for key in ('training_achievement_verified', 'production_deployed'):
        _require(bundle.get(key) is False, 'unverified capability rejected: ' + key)
    if 'normalization' in bundle:
        _require(isinstance(bundle['normalization'], dict), 'normalization required as object')
        _require(bundle['normalization'].get('normalized_hash') == identity['input_hash'],
                 'normalization input binding mismatch')
    raw = None
    if 'raw' in bundle:
        raw = validate(bundle['raw'])
        _require(digest(raw) == identity['input_hash'], 'raw input hash mismatch')
        _require(raw['race']['race_id'] == identity['race_id'] and raw['mode'] == identity['mode'],
                 'raw input identity mismatch')
        _require(timestamp(raw['race']['cutoff']) == timestamp(prediction['cutoff']),
                 'raw/prediction cutoff mismatch')
        _require(set(feature_horses) == {r['horse_id'] for r in raw['runners']}, 'raw/prediction roster mismatch')
        for runner in raw['runners']:
            for key in ('horse_no', 'frame_no', 'barrier_no'):
                _require(feature_horses[runner['horse_id']][key] == runner[key],
                         'raw/prediction ' + key + ' mismatch')
        locked = timestamp(prediction['locked_at'])
        def before_lock(value):
            if isinstance(value, dict):
                if value.get('available_at') is not None:
                    _require(timestamp(value['available_at']) <= locked, 'raw unavailable at lock')
                if value.get('occurred_at') is not None:
                    _require(timestamp(value['occurred_at']) < locked, 'raw history after lock')
                for child in value.values():
                    before_lock(child)
            elif isinstance(value, list):
                for child in value:
                    before_lock(child)
        before_lock(raw)
    if 'racecard' in bundle:
        card = bundle['racecard']
        _require(isinstance(card, list), 'racecard must be an array')
        horses, numbers = set(), set()
        expected = {r['horse_id']: r for r in raw['runners']} if raw is not None else None
        for row in card:
            _require(isinstance(row, dict) and {'horse_id', 'horse_no', 'frame_no'} <= set(row)
                     and set(row) <= {'horse_id', 'horse_no', 'frame_no', 'name', 'barrier_no'},
                     'racecard fields rejected')
            horse = row['horse_id']
            _require(isinstance(horse, str) and horse in prediction.get('win', {})
                     and horse not in horses, 'racecard horse identity mismatch')
            _require(type(row['horse_no']) is int and row['horse_no'] > 0
                     and row['horse_no'] not in numbers
                     and row['horse_no'] == feature_horses[horse]['horse_no'], 'racecard horse number rejected')
            _require(type(row['frame_no']) is int and 1 <= row['frame_no'] <= 8
                     and str(row['frame_no']) == prediction.get('frames', {}).get(horse),
                     'racecard frame mismatch')
            _require('name' not in row or isinstance(row['name'], str), 'racecard name must be text')
            if expected is not None:
                for key in ('horse_no', 'frame_no', 'barrier_no'):
                    if key in row:
                        _require(type(row[key]) is int and row[key] == expected[horse][key],
                                 'racecard/raw ' + key + ' mismatch')
            horses.add(horse)
            numbers.add(row['horse_no'])
        _require(horses == set(prediction.get('win', {})), 'racecard must cover all horses')
    _inspect_payload(_pre_bundle(bundle), identity, 'PRE', prediction['locked_at'])
    if 'settlement' in bundle:
        _settlement(bundle['settlement'], plan)
    if 'learning_review' in bundle:
        review = bundle['learning_review']
        _require(isinstance(review, dict), 'learning review must be an object')
        _require(set(review) == {'schema', 'race_id', 'input_hash', 'prediction_hash',
                                'records_hash', 'result_hash', 'available_at', 'brier_sum', 'status',
                                'input_mode', 'forward_performance_verified',
                                'training_achievement_verified', 'model_parameters_changed', 'review_hash'},
                 'learning review fields rejected')
        _require(review.get('schema') == 'prism.dialogue.learning-review/v1', 'learning review schema rejected')
        for key in ('race_id', 'input_hash', 'prediction_hash'):
            _require(review.get(key) == identity[key], 'learning review ' + key + ' mismatch')
        _require(review.get('input_mode') == identity['mode'], 'learning review input mode mismatch')
        _require(review.get('review_hash') == digest({k: v for k, v in review.items() if k != 'review_hash'}),
                 'learning review hash mismatch')
        for key in ('records_hash', 'result_hash'):
            _hash(review.get(key), key)
        _require(timestamp(review['available_at']) > timestamp(prediction['cutoff']), 'learning review before result')
        _require(type(review['brier_sum']) in (int, float) and isfinite(review['brier_sum'])
                 and review['brier_sum'] >= 0, 'learning review score rejected')
        _require(review['status'] == 'REVIEW_RECORDED_NOT_TRAINED', 'learning review status rejected')
        for key in ('forward_performance_verified', 'training_achievement_verified', 'model_parameters_changed'):
            _require(review[key] is False, 'unverified learning capability rejected')
    # JSON canonicalization also rejects NaN, infinity and unsupported objects.
    digest(bundle)
    return identity


def _plan(plan, candidates, prediction):
    """Verify immutable fixed-unit selection and its candidate membership."""
    _require(isinstance(candidates, list), 'candidate values required')
    by_key = {}
    for candidate in candidates:
        _require(isinstance(candidate, dict), 'candidate object required')
        key = ticket_key(candidate.get('bet_type'), candidate.get('legs'))
        _require(candidate.get('key') == key and key not in by_key, 'candidate key/duplicate rejected')
        legs, kind = candidate['legs'], candidate['bet_type']
        _require(isinstance(legs, list) and (kind not in UNORDERED or legs == sorted(legs)),
                 'candidate leg order rejected')
        frames = list(prediction.get('frames', {}).values())
        if kind == 'FRAME':
            _require(all(leg in frames for leg in legs) and
                     (legs[0] != legs[1] or frames.count(legs[0]) >= 2), 'candidate frame rejected')
        else:
            _require(set(legs) <= set(prediction.get('win', {})), 'candidate horse rejected')
        _require(type(candidate.get('stake_yen')) is int and candidate['stake_yen'] == 100,
                 'candidate fixed stake rejected')
        _require(candidate.get('status') == 'REFERENCE' and candidate.get('market_proxy_is_true_probability') is False,
                 'candidate status/proxy claim rejected')
        probability = numeric(candidate.get('probability'), 0, 1)
        odds = numeric(candidate.get('decimal_odds'), 1, 100000000)
        numeric(candidate.get('quoted_high'), odds, 100000000)
        ev = probability * odds - 1
        for name, expected in (('net_ev', ev), ('expected_profit_yen', 100 * ev), ('gross_return_ratio', ev + 1)):
            actual = numeric(candidate.get(name))
            _require(isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-10), 'candidate Value arithmetic mismatch')
        fair = candidate.get('fair_odds')
        _require(fair is None if probability == 0 else
                 type(fair) in (int, float) and isfinite(fair) and isclose(fair, 1 / probability, rel_tol=1e-12),
                 'candidate fair odds mismatch')
        by_key[key] = candidate
    tickets = plan.get('tickets')
    _require(isinstance(tickets, list) and len(tickets) <= 6, 'plan tickets rejected')
    selected = set()
    for ticket in tickets:
        _require(isinstance(ticket, dict), 'plan ticket required')
        key = ticket_key(ticket.get('bet_type'), ticket.get('legs'))
        _require(ticket.get('key') == key and key not in selected and key in by_key,
                 'plan key/duplicate/membership rejected')
        _require(ticket.get('status') == 'CANDIDATE', 'plan ticket status rejected')
        _require(digest({k: v for k, v in ticket.items() if k != 'status'}) ==
                 digest({k: v for k, v in by_key[key].items() if k != 'status'}),
                 'plan/candidate content mismatch')
        _require(ticket['net_ev'] > 0, 'plan selected nonpositive Value')
        selected.add(key)
    _require(type(plan.get('stake_yen')) is int and plan['stake_yen'] == 100 * len(tickets),
             'plan fixed stake total rejected')
    expected_profit = sum(ticket['expected_profit_yen'] for ticket in tickets)
    _require(isclose(numeric(plan.get('expected_profit_yen')), expected_profit, rel_tol=1e-12, abs_tol=1e-10),
             'plan expected profit mismatch')
    _require(plan.get('decision') == ('CANDIDATES' if tickets else 'NO_BET'), 'plan decision mismatch')


def _settlement(value, plan):
    """Check local arithmetic and plan-ticket binding, not official-result truth."""
    _require(isinstance(value, dict) and set(value) == {'rows', 'gross_stake_yen', 'refund_yen',
             'effective_stake_yen', 'payout_yen', 'profit_yen', 'roi'}, 'settlement fields rejected')
    rows = value['rows']
    _require(isinstance(rows, list), 'settlement rows required')
    keys = []
    for row in rows:
        _require(isinstance(row, dict) and set(row) == {'key', 'stake_yen', 'refund_yen', 'payout_yen', 'profit_yen'},
                 'settlement row fields rejected')
        keys.append(row['key'])
        _require(isinstance(row['key'], str), 'settlement ticket key rejected')
        for key in ('stake_yen', 'refund_yen', 'payout_yen', 'profit_yen'):
            _require(type(row[key]) is int, 'settlement row integer required')
        _require(row['stake_yen'] == 100 and row['refund_yen'] in (0, 100) and row['payout_yen'] >= 0,
                 'settlement fixed stake/refund/payout rejected')
        _require(not row['refund_yen'] or row['payout_yen'] == 0, 'settlement refund/payout conflict')
        _require(row['profit_yen'] == row['payout_yen'] + row['refund_yen'] - 100,
                 'settlement row profit mismatch')
    _require(len(keys) == len(set(keys)) and set(keys) == {t['key'] for t in plan['tickets']},
             'settlement/plan ticket binding mismatch')
    gross = sum(row['stake_yen'] for row in rows)
    refund = sum(row['refund_yen'] for row in rows)
    payout = sum(row['payout_yen'] for row in rows)
    expected = {'gross_stake_yen': gross, 'refund_yen': refund, 'effective_stake_yen': gross - refund,
                'payout_yen': payout, 'profit_yen': payout + refund - gross}
    for key, amount in expected.items():
        _require(type(value[key]) is int and value[key] == amount, 'settlement total mismatch: ' + key)
    _require(plan['stake_yen'] == gross, 'settlement/plan stake mismatch')
    if gross == refund:
        _require(value['roi'] is None, 'fully refunded ROI must be null')
    else:
        _require(type(value['roi']) in (int, float) and isfinite(value['roi'])
                 and value['roi'] == payout / (gross - refund), 'settlement ROI mismatch')


def _pre_bundle(bundle):
    # The allowlist deliberately excludes settlement and every future POST field.
    return {key: bundle[key] for key in ('schema', 'prediction', 'market_values', 'normalization', 'raw', 'racecard')
            if key in bundle}


def _inspect_payload(value, identity, stage, locked_at):
    if isinstance(value, dict):
        schema = value.get('schema')
        if isinstance(schema, str) and schema.startswith('prism.records.race-memory/'):
            _require(schema == 'prism.records.race-memory/v1', 'unknown race-memory schema')
        if value.get('schema') == 'prism.records.race-memory/v1':
            # A frozen, as-of entity-memory snapshot has an explicit historical
            # identity namespace. Only its dedicated validator can cross that
            # boundary; ordinary nested race IDs still bind to the current race.
            from prism_records.memory import verify_race_memory
            _require(verify_race_memory(value, identity['race_id'], as_of=locked_at) is True,
                     'race-memory validation failed')
            return
        for key, item in value.items():
            if key in _BINDINGS:
                _require(item == identity[key], 'artifact ' + key + ' mismatch')
            if key == 'stage' and item in ('PRE', 'POST'):
                _require(item == stage, 'artifact stage mismatch')
            if stage == 'PRE' and key in _POST_KEYS:
                # A false marker is a useful explicit PRE guarantee, not a reveal.
                _require(key == 'result_revealed' and item is False,
                         'result-bearing field forbidden in PRE: ' + key)
            _inspect_payload(item, identity, stage, locked_at)
    elif isinstance(value, list):
        for item in value:
            _inspect_payload(item, identity, stage, locked_at)


def _artifacts(bundle, artifacts):
    identity = _identity(bundle)
    _require(artifacts is None or isinstance(artifacts, dict), 'artifacts must be a mapping')
    artifacts = {} if artifacts is None else artifacts
    descriptors = {}
    for kind, artifact in artifacts.items():
        _require(isinstance(kind, str) and _KIND.fullmatch(kind), 'artifact kind rejected')
        _require(isinstance(artifact, dict) and set(artifact) <= {'stage', 'payload', 'depends_on'}
                 and {'stage', 'payload'} <= set(artifact), 'artifact envelope rejected')
        stage = artifact['stage']
        _require(stage in {'PRE', 'POST'}, 'artifact stage rejected')
        dependencies = artifact.get('depends_on', [])
        _require(isinstance(dependencies, list) and all(isinstance(k, str) for k in dependencies),
                 'artifact dependencies must be strings')
        _require(len(dependencies) == len(set(dependencies)), 'duplicate dependency')
        _inspect_payload(artifact['payload'], identity, stage, bundle['prediction']['locked_at'])
        payload_hash = digest(artifact['payload'])
        context_hash = digest(_pre_bundle(bundle)) if stage == 'PRE' else digest(bundle)
        cache_key = digest({'schema': SCHEMA, **identity, 'kind': kind, 'stage': stage,
                            'context_hash': context_hash, 'payload_hash': payload_hash,
                            'depends_on': sorted(dependencies)})
        descriptors[kind] = {'stage': stage, 'payload_hash': payload_hash,
                             'depends_on': sorted(dependencies), 'cache_key': cache_key}
    for kind, descriptor in descriptors.items():
        for dependency in descriptor['depends_on']:
            _require(dependency in descriptors and dependency != kind, 'missing/self dependency')
            _require(not (descriptor['stage'] == 'PRE' and descriptors[dependency]['stage'] == 'POST'),
                     'PRE cannot depend on POST')
    # Detect all cycles, including POST-only cycles which are not temporal leaks.
    visiting, done = set(), set()
    def visit(kind):
        _require(kind not in visiting, 'artifact dependency cycle')
        if kind in done:
            return
        visiting.add(kind)
        for dependency in descriptors[kind]['depends_on']:
            visit(dependency)
        visiting.remove(kind)
        done.add(kind)
    for kind in descriptors:
        visit(kind)
    # Bind transitive dependency contents as well as their names into cache keys.
    def seal(kind):
        descriptor = descriptors[kind]
        return digest({'local_cache_key': descriptor['cache_key'],
                       'dependencies': {dep: seal(dep) for dep in descriptor['depends_on']}})
    sealed = {kind: seal(kind) for kind in descriptors}
    for kind in descriptors:
        descriptors[kind]['cache_key'] = sealed[kind]
    return identity, descriptors


def build_manifest(bundle, artifacts=None):
    """Build a deterministic manifest without certifying the upstream sources."""
    identity, descriptors = _artifacts(bundle, artifacts)
    prediction = bundle['prediction']
    manifest = {
        'schema': SCHEMA, **identity, 'bundle_hash': digest(bundle),
        'pre_bundle_hash': digest(_pre_bundle(bundle)), 'artifacts': descriptors,
        'provenance': {
            'input_hash': identity['input_hash'], 'prediction_hash': identity['prediction_hash'],
            'locked_at': prediction['locked_at'], 'cutoff': prediction['cutoff'],
            'declared_input_mode': identity['mode'],
            'normalization': deepcopy(bundle.get('normalization')),
            'source_ref': deepcopy(bundle['raw']['source']) if 'raw' in bundle else None,
            'timestamp_scope': ('DECLARED_ENGINE_TIMESTAMPS_ONLY' if identity['mode'] == 'PRE_AVAILABLE'
                                else 'NOT_FORWARD_CERTIFIED'),
            'raw_input_payload_reverified': 'raw' in bundle, 'source_authenticity_verified': False,
            'strict_pit_certified': False,
        },
        'integrity_scope': 'SHA256 integrity and identity binding; not signatures or source truth',
        'pre_leakage_check': 'Known result-bearing keys and explicit dependency stages; not semantic proof',
        'performance_validated': False, 'training_achievement_verified': False,
        'production_deployed': False, 'execution_allowed': False,
    }
    manifest['manifest_hash'] = digest(manifest)
    return manifest


def verify_manifest(manifest, bundle, artifacts=None):
    """Raise ValueError on changes or mismatched inputs; return True otherwise."""
    _require(isinstance(manifest, dict), 'manifest must be an object')
    # Canonical JSON comparison preserves boolean/integer distinctions which
    # Python object equality would collapse (False == 0, True == 1).
    _require(digest(manifest) == digest(build_manifest(bundle, artifacts)),
             'manifest content/binding mismatch')
    return True


def artifact_cache_key(bundle, kind, payload, stage='PRE'):
    """Cache key for one independent artifact (use manifest for dependency graphs)."""
    return build_manifest(bundle, {kind: {'stage': stage, 'payload': payload}})['artifacts'][kind]['cache_key']


def write_manifest(path, manifest, bundle, artifacts=None):
    """Idempotent local write; refuse differing content at an existing path."""
    verify_manifest(manifest, bundle, artifacts)
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        _require(path.read_text(encoding='utf-8') == serialized, 'refuse manifest overwrite')
    else:
        with path.open('x', encoding='utf-8') as handle:
            handle.write(serialized)
    return manifest['manifest_hash']
