"""Resumable initial predictions → discussion → final predictions → paper.

No mock/provider failure can become a successful official publication.
"""
from copy import deepcopy
from pathlib import Path

from prism_engine import predict
from prism_engine.contracts import digest, timestamp
from prism_pre_day_gate import check_publication
from .store import utcnow

TOPICS = (
    ('full-field', '全頭評価と見落とし'),
    ('pace-track', '展開・コース・馬場とトラックバイアス'),
    ('condition', '状態・調教・ローテーション'),
    ('challenge', '専門家推奨への反証・少数意見'),
    ('tickets', '100円単位の具体的買い目と見送り'),
)


def operation_race(card, snapshot):
    """Keep official identities, including not-yet-assigned draw numbers."""
    from .characters import verify_character_snapshot
    verify_character_snapshot(snapshot)
    if card.get('source_verified') is not True:
        raise ValueError('BLOCKED_OFFICIAL_IDENTITY')
    return {
        'race_id': card['race_id'], 'authority': card['authority'],
        'race_name': card['race_name'], 'start_at': card.get('start_at', card.get('off_at')),
        'declaration_stage': card.get('declaration_stage', 'DRAW_CONFIRMED'),
        'runners': [dict(r, name=r.get('name', r.get('horse_name')))
                    for r in card.get('active_runners', card.get('runners', []))
                    if r.get('status', 'DECLARED') == 'DECLARED'],
        'required_forecasters': [r['agent_id'] for r in snapshot['records']],
        'character_snapshot_hash': snapshot['snapshot_hash'],
        'source_refs': [card.get('official_url')],
    }


def run_pre_day(race, character_snapshot, core_raw, store, provider, *,
                edition='pre-v1', now=utcnow, render=True):
    from .characters import get_character, verify_character_snapshot
    from .provider import validate_execution
    verify_character_snapshot(character_snapshot)
    race_id = race['race_id']
    with store.lock(race_id):
        try:
            if timestamp(now()) >= timestamp(race['start_at']):
                raise ValueError('DEADLINE_PASSED_NO_BACKDATING')
            if race['character_snapshot_hash'] != character_snapshot['snapshot_hash']:
                raise ValueError('CHARACTER_SNAPSHOT_CHANGED')
            store.save(race_id, 'characters', edition, character_snapshot)
            store.save(race_id, 'race', edition, race)
            if core_raw is None:
                raise ValueError('BLOCKED_SOURCE_EVIDENCE: canonical core input required')
            if core_raw['race']['race_id'] != race_id:
                raise ValueError('CORE_RACE_ID_MISMATCH')
            if ({r.get('horse_id') for r in core_raw.get('runners', [])} !=
                    {r.get('horse_id') for r in race['runners']}):
                raise ValueError('CORE_RUNNER_IDENTITY_MISMATCH')
            if timestamp(core_raw['race']['cutoff']) != timestamp(race['start_at']):
                raise ValueError('CORE_RACE_START_MISMATCH')
            if core_raw['race'].get('declaration_stage','DRAW_CONFIRMED') != race.get('declaration_stage','DRAW_CONFIRMED'):
                raise ValueError('CORE_DECLARATION_STAGE_MISMATCH')
            official_runners={r['horse_id']:r for r in race['runners']}
            for runner in core_raw['runners']:
                official=official_runners[runner['horse_id']]
                if any(runner.get(k)!=official.get(k) for k in ('horse_no','frame_no')):
                    raise ValueError('CORE_OFFICIAL_DRAW_MISMATCH')
            core_entry = store.get(race_id, 'core', edition)
            if core_entry is None:
                locked_at = now()
                lock = predict(core_raw, locked_at)
                core_entry = store.save(race_id, 'core', edition,
                                        {'raw': core_raw, 'prediction': lock})
            elif digest(core_raw) != digest(core_entry['payload']['raw']):
                raise ValueError('CORE_INPUT_CHANGED_USE_NEW_EDITION')
            core = core_entry['payload']['prediction']
            ordered_ids = [r['agent_id'] for r in sorted(character_snapshot['records'],
                key=lambda r: ({'editor': 0, 'reporter': 1, 'specialist': 2}.get(r['role'], 3), r['agent_id']))]
            if set(ordered_ids) != set(race['required_forecasters']):
                raise ValueError('CHARACTER_ROSTER_MISMATCH')
            base = {'race_id': race_id, 'race': race, 'runners': race['runners'],
                    'character_snapshot_hash': race['character_snapshot_hash'],
                    'core_prediction': core, 'source_refs': race.get('source_refs', [])}
            receipts = {}

            def execute(agent_id, stage, context, key):
                if timestamp(now()) >= timestamp(race['start_at']):
                    raise ValueError('DEADLINE_PASSED_DURING_EXECUTION')
                character = get_character(character_snapshot, agent_id)
                if character['role']=='editor' and stage in {'PRELIMINARY','FINAL'}:
                    # The editorial prediction is a separate call attributed to
                    # 本紙. Retain the canonical editor UUID/configuration; this
                    # byline does not create another persona or rename the chair.
                    context=dict(context,output_attribution={'byline':'本紙','role':'EDITORIAL'})
                cached = store.get(race_id, 'executions', key)
                if cached is None:
                    result = provider.predict(context, character, stage=stage)
                    validate_execution(result, context=context, character=character)
                    cached = store.save(race_id, 'executions', key, result)
                result = deepcopy(cached['payload'])
                validate_execution(result, context=context, character=character)
                result['persisted_at'] = cached['persisted_at']
                if timestamp(now()) >= timestamp(race['start_at']):
                    raise ValueError('DEADLINE_PASSED_DURING_EXECUTION')
                previous=receipts.get(result['receipt']['execution_id'])
                if previous is not None and previous['output']!=result['output']:
                    raise ValueError('DUPLICATE_EXECUTION_ID_DIFFERENT_OUTPUT')
                receipts[result['receipt']['execution_id']] = result
                return result['output']

            preliminary = {}
            for agent_id in ordered_ids:
                preliminary[agent_id] = execute(agent_id, 'PRELIMINARY', base,
                                                edition + '-initial-' + agent_id)
            store.save(race_id, 'preliminary', edition, preliminary)
            discussions = []
            for topic_id, title in TOPICS:
                cached = store.get(race_id, 'topics', edition + '-' + topic_id)
                started = store.get(race_id, 'topic-start', edition + '-' + topic_id)
                if cached:
                    topic = cached['payload']
                elif started:
                    topic = started['payload']
                else:
                    topic = {'topic_id': topic_id, 'title': title, 'started_at': now(),
                             'facilitator': 'SHINOMIYA_RITSU', 'newcomer': 'RIO', 'turns': []}
                    store.save(race_id, 'topic-start', edition + '-' + topic_id, topic)
                # Replay already-saved model calls using the same input hashes.
                turns = []
                for agent_id in ordered_ids:
                    context = dict(base, preliminary=preliminary,
                                   previous_topics=discussions,
                                   topic={'topic_id': topic_id, 'title': title},
                                   prior_turns=turns)
                    turn = execute(agent_id, 'RESPONSE', context,
                                   edition + '-' + topic_id + '-' + agent_id)
                    turns.append(turn)
                if cached is None:
                    topic.update(turns=turns, completed_at=now())
                    store.save(race_id, 'topics', edition + '-' + topic_id, topic)
                elif topic['turns'] != turns:
                    raise ValueError('DISCUSSION_REPLAY_MISMATCH')
                discussions.append(topic)
            final = {}
            for agent_id in ordered_ids:
                context = dict(base, preliminary=preliminary, discussions=discussions)
                final[agent_id] = execute(agent_id, 'FINAL', context,
                                         edition + '-final-' + agent_id)
            bundle = {'schema': 'prism.ops.publication_bundle/v1', 'race': race,
                      'characters':character_snapshot['records'],'mode':core['mode'],
                      'source_refs':race.get('source_refs',[]),
                      'core_prediction': core, 'preliminary': preliminary,
                      'discussions': discussions, 'final': final}
            store.save(race_id, 'bundle', edition, bundle)
            store.save(race_id, 'receipts', edition, receipts)
            paper = None
            if render:
                from .paper import render_operational_paper
                cached = store.get(race_id, 'paper', edition)
                if cached:
                    paper = cached['payload']
                else:
                    paper = render_operational_paper(bundle,
                        store.directory / 'papers' / race_id / edition, version=edition)
                    store.save(race_id, 'paper', edition, paper)
            store.status(race_id, 'AWAITING_VISUAL_QA' if render else 'EXECUTED',
                         {'edition': edition, 'bundle_hash': digest(bundle),
                          'independent_executions': sum(
                              r['receipt']['execution_mode'] == 'INDEPENDENT_EXECUTION'
                              for r in receipts.values()), 'official_publications': 0})
            return {'bundle': bundle, 'execution_receipts': receipts, 'paper': paper}
        except Exception as exc:
            store.status(race_id, 'BLOCKED', {'edition': edition,
                         'reason': type(exc).__name__ + ': ' + str(exc)[:300],
                         'official_publications': 0})
            raise


def publish_saved(store, race_id, paper, *, edition='pre-v1', now=utcnow):
    with store.lock(race_id):
        published = store.get(race_id,'publication',edition)
        if published is not None:
            previous=published['payload']['paper']
            if (not isinstance(paper,dict) or paper.get('manifest_hash')!=previous.get('manifest_hash') or
                    digest(paper)!=digest(previous)):
                raise ValueError('PUBLISHED_PAPER_CHANGED_USE_NEW_EDITION')
            return published['payload']['gate']
        bundle_entry = store.get(race_id, 'bundle', edition)
        receipt_entry = store.get(race_id, 'receipts', edition)
        if bundle_entry is None or receipt_entry is None:
            raise ValueError('PUBLICATION_INPUTS_NOT_SAVED')
        bundle = bundle_entry['payload']
        receipts = receipt_entry['payload']
        published_at = now()
        report = check_publication(bundle['race'], bundle['preliminary'],
                                   bundle['discussions'], bundle['final'], published_at,
                                   execution_receipts=receipts, paper=paper,
                                   publication_content_hash=digest(bundle))
        store.save(race_id, 'publication-check', edition + '-' + digest(report)[:12], report)
        if report['ready']:
            store.save(race_id, 'publication', edition,
                       {'bundle_hash': digest(bundle), 'paper': paper,
                        'published_at': published_at, 'gate': report})
            store.status(race_id, 'VERIFIED', {'edition': edition, 'publication': True,
                                              'production_deployed': False})
        else:
            store.status(race_id, 'BLOCKED_PUBLICATION', report)
        return report
