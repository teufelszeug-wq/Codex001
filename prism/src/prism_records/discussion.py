"""Persist attributed discussion claims, never promote them to measured facts.

Templates retain their entire source document but produce zero assessment rows.
Simulation/independence are declared modes; neither proves independent execution.
"""
import json
from prism_engine.contracts import digest, fields, timestamp
from prism_dialogue import validate_discussion


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _insert(conn, table, row):
    """Replay exact rows; never silently update an existing record identity."""
    existing = conn.execute('SELECT * FROM ' + table + ' WHERE id=?', (row['id'],)).fetchone()
    if existing:
        if any(existing[k] != value for k, value in row.items()):
            raise ValueError('immutable record conflict: ' + table)
        return False
    cols = list(row)
    conn.execute('INSERT INTO ' + table + ' (' + ','.join(cols) + ') VALUES (' + ','.join('?' for _ in cols) + ')',
                 [row[k] for k in cols])
    return True


def save_discussion(store, context, records, horse_map, jockey_map=None, review=None, jockey_subject_turn_ids=()):
    """Atomically save PRE records, attributed claims and an optional separate POST review.

    horse_map maps every context horse identity to an existing DB horse identity.
    References must agree with the race's existing entry, including horse number.
    PRE observations are not upserted and identities/availability are not upgraded.
    """
    audit = validate_discussion(context, records)
    if audit['status'] != 'STRUCTURAL_PASS': raise ValueError('discussion gate failed: ' + ','.join(audit['errors']))
    roster = {r['horse_id']: r for r in context['roster']}
    if not isinstance(horse_map, dict) or set(horse_map) != set(roster): raise ValueError('complete horse mapping required')
    if any(not isinstance(x, str) or not x for x in horse_map.values()) or len(set(horse_map.values())) != len(horse_map):
        raise ValueError('ambiguous horse mapping')
    jockey_map = {} if jockey_map is None else jockey_map
    if not isinstance(jockey_map, dict) or not set(jockey_map) <= set(roster): raise ValueError('unknown jockey mapping key')
    if any(not isinstance(x, str) or not x for x in jockey_map.values()): raise ValueError('jockey identity required')
    if not isinstance(jockey_subject_turn_ids, (list, tuple)) or any(not isinstance(x, str) for x in jockey_subject_turn_ids):
        raise ValueError('explicit jockey subject turn IDs required')
    jockey_subjects = set(jockey_subject_turn_ids)
    if len(jockey_subjects) != len(jockey_subject_turn_ids): raise ValueError('duplicate jockey subject assignment')
    turns_by_id = {t['turn_id']: t for t in records['turns']}
    selections_by_turn = {s['turn_id']: s for s in records.get('selections', [])}
    if jockey_subjects & set(selections_by_turn):
        raise ValueError('horse selection cannot be assigned to a direct jockey judgment')
    for tid in jockey_subjects:
        t = turns_by_id.get(tid)
        if t is None or t['stage'] not in {'INITIAL', 'RESPONSE', 'FINAL'} or t['horse_id'] not in jockey_map:
            raise ValueError('jockey subject needs an assessment turn and explicit rider mapping')
    if review is not None:
        fields(review, {'schema', 'race_id', 'input_hash', 'prediction_hash', 'records_hash', 'result_hash',
                        'available_at', 'brier_sum', 'status', 'input_mode', 'forward_performance_verified',
                        'training_achievement_verified', 'model_parameters_changed', 'review_hash'},
               {'schema', 'race_id', 'input_hash', 'prediction_hash', 'records_hash', 'result_hash',
                'available_at', 'brier_sum', 'status', 'input_mode', 'forward_performance_verified',
                'training_achievement_verified', 'model_parameters_changed', 'review_hash'})
        if review['schema'] != 'prism.dialogue.learning-review/v1' or review['review_hash'] != digest({k:v for k,v in review.items() if k != 'review_hash'}):
            raise ValueError('POST review integrity')
        if any(review[k] != context[k] for k in ('race_id', 'input_hash', 'prediction_hash', 'input_mode')):
            raise ValueError('POST review binding')
        if review['records_hash'] != audit['records_hash'] or timestamp(review['available_at']) <= timestamp(context['cutoff']):
            raise ValueError('POST review time/records')
        if review['status'] != 'REVIEW_RECORDED_NOT_TRAINED' or any(review[k] is not False for k in ('forward_performance_verified', 'training_achievement_verified', 'model_parameters_changed')):
            raise ValueError('unattested learning claim')
    conn = store.connection
    bindings = {k: context[k] for k in ('race_id', 'input_hash', 'prediction_hash')}
    discussion_id = 'discussion:pre:' + audit['records_hash']
    declared_mode = records['execution_mode']
    payload = {'context': context, 'records': records, 'audit': audit, 'horse_map': horse_map,
               'jockey_map': jockey_map, 'jockey_subject_turn_ids': sorted(jockey_subjects),
               'claim_type': 'SUPPLIED_DIALOGUE_NOT_OBSERVED_FACT',
               'verified_independent': False, 'training_achievement_verified': False}
    inserted = 0; assessment_ids = []; post_id = None
    with store.transaction():
        race_row = conn.execute('SELECT metadata_json FROM races WHERE id=?', (context['race_id'],)).fetchone()
        if race_row is None: raise ValueError('missing race identity')
        race_metadata = json.loads(race_row[0])
        db_cutoff = race_metadata.get('cutoff')
        if db_cutoff is not None:
            db_time = timestamp(db_cutoff)
            if timestamp(context['cutoff']) != db_time or timestamp(records['recorded_at']) > db_time:
                raise ValueError('discussion/database cutoff mismatch')
        elif context['input_mode'] not in {'SYNTHETIC', 'HISTORICAL_RECONSTRUCTION'}:
            raise ValueError('unknown database cutoff cannot certify PRE_AVAILABLE')
        time_provenance = {'database_cutoff': db_cutoff,
                           'temporal_class': 'UNKNOWN_RACE_CUTOFF' if db_cutoff is None else 'CUTOFF_MATCHED_NOT_ATTESTED',
                           'input_mode': context['input_mode'], 'externally_attested': False,
                           'note': 'PRE denotes meeting phase, not authenticated pre-race availability.'}
        payload['time_provenance'] = time_provenance
        entries = {}
        for horse, db_horse in horse_map.items():
            row = conn.execute('SELECT id,horse_id,jockey_id,horse_no,frame_no FROM entries WHERE race_id=? AND horse_id=?',
                               (context['race_id'], db_horse)).fetchone()
            if row is None or row[3] != roster[horse]['horse_no'] or row[4] != roster[horse]['frame_no']:
                raise ValueError('discussion horse/entry mismatch')
            if conn.execute('SELECT id FROM horses WHERE id=?', (db_horse,)).fetchone() is None:
                raise ValueError('missing horse identity')
            if horse in jockey_map and jockey_map[horse] != row[2]: raise ValueError('jockey/entry mismatch')
            if row[2] is not None and conn.execute('SELECT id FROM jockeys WHERE id=?', (row[2],)).fetchone() is None:
                raise ValueError('missing jockey identity')
            entries[horse] = tuple(row)
        _insert(conn, 'discussions', {'id': discussion_id, 'race_id': context['race_id'], 'phase': 'PRE',
                'occurred_at': records['recorded_at'], 'mode': declared_mode, 'prediction_hash': context['prediction_hash'],
                'payload_json': _json(payload), 'content_hash': digest(payload)})
        if declared_mode != 'TEMPLATE':
            for turn in records['turns']:
                horse = turn['horse_id']
                if horse is None or turn['stage'] not in {'INITIAL', 'RESPONSE', 'FINAL'}: continue
                entry = entries[horse]
                subject = 'JOCKEY' if turn['turn_id'] in jockey_subjects else 'HORSE'
                aid = 'assessment:' + digest({'discussion': discussion_id, 'turn_id': turn['turn_id']})
                assessment_ids.append(aid)
                claim = {**bindings, 'turn': turn, 'evidence_refs': turn['evidence_refs'],
                         'context_hash': context['context_hash'], 'records_hash': audit['records_hash'],
                         'entry_id': entry[0], 'horse_id': entry[1], 'jockey_id': entry[2],
                         'subject_type': subject,
                         'selection': selections_by_turn.get(turn['turn_id']) if turn['stage'] == 'FINAL' else None,
                         'jockey_relationship': 'EXPLICIT_SUBJECT' if subject == 'JOCKEY' else 'RELATED_RIDER_NOT_DIRECT_ASSESSMENT',
                         'semantic_subject_verified': False,
                         'input_mode': context['input_mode'], 'execution_mode': declared_mode,
                         'time_provenance': time_provenance,
                         'claim_type': 'ATTRIBUTED_OPINION_NOT_OBSERVED_FACT',
                         'verified_independent': False, 'training_achievement_verified': False}
                inserted += _insert(conn, 'assessments', {'id': aid, 'discussion_id': discussion_id,
                        'entry_id': entry[0], 'horse_id': entry[1], 'jockey_id': entry[2], 'phase': 'PRE',
                        'mode': declared_mode, 'prediction_hash': context['prediction_hash'],
                        'agent_id': turn['agent_id'], 'turn_id': turn['turn_id'],
                        'subject_type': subject,
                        'claim_type': 'ATTRIBUTED_OPINION_NOT_OBSERVED_FACT', 'verified_independent': 0,
                        'training_achievement_verified': 0, 'payload_json': _json(claim), 'content_hash': digest(claim)})
        if review is not None:
            post_id = 'discussion:post:' + review['review_hash']
            post = {'review': review, 'pre_discussion_id': discussion_id, **bindings,
                    'time_provenance': time_provenance,
                    'claim_type': 'POST_REVIEW_NOT_TRAINING', 'verified_independent': False,
                    'training_achievement_verified': False}
            _insert(conn, 'discussions', {'id': post_id, 'race_id': context['race_id'], 'phase': 'POST',
                    'occurred_at': review['available_at'], 'mode': declared_mode,
                    'prediction_hash': context['prediction_hash'], 'payload_json': _json(post), 'content_hash': digest(post)})
    return {'discussion_id': discussion_id, 'post_review_id': post_id, 'assessment_ids': assessment_ids,
            'inserted_assessment_rows': inserted, 'assessment_rows': len(assessment_ids),
            'actual_verified_assessments': 0, 'execution_mode': declared_mode,
            'independent_execution_verified': False, 'training_achievement_verified': False}
