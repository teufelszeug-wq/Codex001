"""Settle immutable saved publications; POST evidence never rewrites predictions.

The explicit synthetic entrypoint exercises software only. A normal settlement
requires an accepted publication and complete independent provider transcripts.
Reviews below are computed observations, not invented AI reflections or training.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import subprocess
from zoneinfo import ZoneInfo

from prism_engine.contracts import digest, timestamp
from prism_pre_day_gate import check_publication
from .provider import validate_execution
from .store import utcnow

CLI = Path(__file__).resolve().parents[2] / 'scripts' / 'settle_official.mjs'


def _node(document):
    executable = shutil.which('node')
    if executable is None:
        raise RuntimeError('BLOCKED_NODE_RUNTIME_MISSING')
    completed = subprocess.run([executable, str(CLI)], input=json.dumps(document, ensure_ascii=False, allow_nan=False),
                               capture_output=True, text=True, timeout=30, check=False)
    if completed.returncode:
        try:
            reason = json.loads(completed.stderr)['error']
        except (ValueError, KeyError):
            reason = 'Node settlement bridge failed'
        raise ValueError('BLOCKED_SETTLEMENT: ' + str(reason)[:300])
    return json.loads(completed.stdout)


def _get(store, race_id, kind, edition):
    artifact = store.get(race_id, kind, edition)
    if artifact is None:
        raise ValueError('BLOCKED_SAVED_' + kind.upper() + '_MISSING')
    return artifact


def _validate_saved(store, race_id, edition, observed_at, *, synthetic=False):
    kind = 'synthetic-publication' if synthetic else 'publication'
    publication_artifact = _get(store, race_id, kind, edition)
    publication = publication_artifact['payload']
    bundle_artifact = _get(store, race_id, 'bundle', edition)
    bundle = bundle_artifact['payload']
    receipts = _get(store, race_id, 'receipts', edition)['payload']
    race = bundle['race']
    if race['race_id'] != race_id or publication.get('bundle_hash') != bundle_artifact['content_hash']:
        raise ValueError('BLOCKED_PUBLICATION_BUNDLE_BINDING')
    published_at = publication['published_at']
    if not timestamp(published_at) <= timestamp(publication_artifact['persisted_at']) <= timestamp(observed_at):
        raise ValueError('BLOCKED_PUBLICATION_SAVE_TIMESTAMP')
    if timestamp(publication_artifact['persisted_at']) >= timestamp(race['start_at']):
        raise ValueError('BLOCKED_PUBLICATION_PERSISTED_AFTER_START')
    if timestamp(observed_at) < timestamp(race['start_at']):
        raise ValueError('BLOCKED_RESULT_BEFORE_START')
    if synthetic:
        if publication.get('mode') != 'SYNTHETIC':
            raise ValueError('BLOCKED_SYNTHETIC_PUBLICATION_REQUIRED')
    else:
        if publication.get('mode') == 'SYNTHETIC' or publication.get('gate', {}).get('ready') is not True:
            raise ValueError('BLOCKED_ACCEPTED_PUBLICATION_REQUIRED')
        if publication.get('edition_type') == 'DAY_DELTA' or publication.get('edition_kind') == 'DAY_CORRECTION':
            base_edition = publication.get('base_edition')
            if not base_edition or base_edition == edition:
                raise ValueError('BLOCKED_DAY_DELTA_BASE_REQUIRED')
            base_saved = _get(store, race_id, 'publication', base_edition)['payload']
            if base_saved.get('edition_kind') == 'DAY_CORRECTION' or base_saved.get('edition_type') == 'DAY_DELTA':
                raise ValueError('BLOCKED_DAY_DELTA_REQUIRES_PRE_DAY_BASE')
            base_publication, base_bundle, _ = _validate_saved(store, race_id, base_edition, observed_at)
            if (publication.get('base_bundle_hash') != digest(base_bundle) or
                    bundle.get('base_bundle_hash') != digest(base_bundle) or
                    timestamp(published_at) <= timestamp(base_publication['published_at'])):
                raise ValueError('BLOCKED_DAY_DELTA_BASE_BINDING')
            if not bundle.get('changes') or not bundle.get('change_reason'):
                raise ValueError('BLOCKED_DAY_DELTA_REASON_REQUIRED')
            from prism_pre_day_gate import DAY_DELTA_FIELDS
            if not isinstance(bundle['changes'], dict) or not set(bundle['changes']) <= DAY_DELTA_FIELDS:
                raise ValueError('BLOCKED_DAY_DELTA_FIELDS')
            if timestamp(published_at) >= timestamp(race['start_at']):
                raise ValueError('BLOCKED_DAY_DELTA_AFTER_START')
            from .daydelta import check_day_publication
            report = check_day_publication(store, race_id, publication.get('paper'), version=edition,
                                           published_at=published_at, checked_at=observed_at)
            if not report['ready']:
                raise ValueError('BLOCKED_DAY_PUBLICATION_RECHECK: ' + ','.join(report['errors']))
        else:
            jst = ZoneInfo('Asia/Tokyo')
            if timestamp(publication_artifact['persisted_at']).astimezone(jst).date() >= timestamp(race['start_at']).astimezone(jst).date():
                raise ValueError('BLOCKED_PRE_DAY_PUBLICATION_PERSISTED_LATE')
            report = check_publication(race, bundle['preliminary'], bundle['discussions'], bundle['final'],
                                       published_at, execution_receipts=receipts,
                                       paper=publication.get('paper'), publication_content_hash=digest(bundle),
                                       checked_at=observed_at)
            if not report['ready']:
                raise ValueError('BLOCKED_PUBLICATION_RECHECK: ' + ','.join(report['errors']))
    required = set(race['required_forecasters'])
    if not required or set(bundle['final']) != required:
        raise ValueError('BLOCKED_FINAL_FORECAST_COVERAGE')
    execution_ids = set()
    for author, record in bundle['final'].items():
        evidence = receipts.get(record.get('execution_id'))
        if evidence is None or evidence.get('output') != record:
            raise ValueError('BLOCKED_FINAL_RECEIPT_BINDING')
        validate_execution(evidence, require_independent=not synthetic)
        receipt = evidence['receipt']
        if synthetic and receipt['execution_mode'] != 'SYNTHETIC':
            raise ValueError('BLOCKED_SYNTHETIC_TRANSCRIPT_REQUIRED')
        if (record['race_id'] != race_id or record['stage'] != 'FINAL' or record['forecaster_id'] != author or
                record['character_snapshot_hash'] != race['character_snapshot_hash'] or
                record['execution_id'] in execution_ids or
                not timestamp(record['saved_at']) <= timestamp(evidence['persisted_at']) <= timestamp(published_at)):
            raise ValueError('BLOCKED_FINAL_EXECUTION_BINDING')
        execution_ids.add(record['execution_id'])
    return publication, bundle, receipts


def _forecast_input(bundle, receipts, published_at):
    race = bundle['race']
    runners = race['runners']
    numbers = {runner['horse_id']: runner['horse_no'] for runner in runners}
    if (len(numbers) != len(runners) or any(type(n) is not int or n < 1 for n in numbers.values()) or
            len(set(numbers.values())) != len(numbers)):
        raise ValueError('BLOCKED_CONFIRMED_RUNNER_NUMBERS_REQUIRED')
    records = []
    for author, record in bundle['final'].items():
        diagnoses = []
        for diagnosis in record['diagnoses']:
            if diagnosis['horse_id'] not in numbers:
                raise ValueError('BLOCKED_DIAGNOSIS_IDENTITY')
            diagnoses.append({**deepcopy(diagnosis), 'horse_no':numbers[diagnosis['horse_id']]})
        picks = [{**deepcopy(pick), 'horse_no':numbers[pick['horse_id']]} for pick in record['picks']]
        records.append({**deepcopy(record), 'forecaster_id':author, 'diagnoses':diagnoses,
                        'picks':picks, 'independent_execution':record['mode'] == 'independent_execution',
                        'persisted_at':receipts[record['execution_id']]['persisted_at']})
    return {'race_id':race['race_id'], 'race_name':race['race_name'], 'off_at':race['start_at'],
            'saved_at':published_at, 'source_refs':race.get('source_refs', []),
            'runners':[{'horse_no':r['horse_no'], 'horse_id':r['horse_id'],
                        'frame_no':r.get('frame_no'), 'horse_name':r.get('name', r.get('horse_name'))}
                       for r in runners], 'records':records}


def _outcome(bundle, result):
    known = ('WIN' in result.get('complete_bet_types', []) or
             result.get('mode') == 'SYNTHETIC' and result.get('complete_payouts') is True)
    winners = {p['horse_nos'][0] for p in result.get('payouts', [])
               if p.get('type') == 'WIN' and len(p.get('horse_nos', [])) == 1}
    if result.get('status') == 'CANCELLED' or not known or not winners:
        return {'status':'UNKNOWN', 'winner_horse_nos':[], 'core_brier':None,
                'reason':'complete official WIN outcomes unavailable or race cancelled'}
    runners = bundle['race']['runners']
    probabilities = bundle.get('core_prediction', {}).get('win', {})
    brier = None
    if (set(probabilities) == {r['horse_id'] for r in runners} and
            all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probabilities.values()) and
            abs(sum(probabilities.values()) - 1) < 1e-6):
        brier = sum((probabilities[r['horse_id']] - (1 / len(winners) if r['horse_no'] in winners else 0)) ** 2 for r in runners)
    return {'status':'KNOWN', 'winner_horse_nos':sorted(winners), 'core_brier':brier,
            'brier_scope':'CORE_WIN_PROBABILITIES_FRACTIONAL_DEAD_HEAT_TARGET_NOT_AI_MARK_PROBABILITIES'}


def _settle_saved(store, race_id, result, *, edition, now, synthetic):
    Store = type(store)
    Store.safe(race_id); Store.safe(edition)
    with store.lock(race_id):
        observed_at = now()
        publication, bundle, receipts = _validate_saved(store, race_id, edition, observed_at, synthetic=synthetic)
        if (result.get('mode') == 'SYNTHETIC') != synthetic:
            raise ValueError('BLOCKED_SYNTHETIC_OFFICIAL_RESULT_MISMATCH')
        forecast = _node({'operation':'create_forecast', 'forecast_input':_forecast_input(bundle, receipts, publication['published_at'])})
        settlement = _node({'forecast':forecast, 'result':result, 'settled_at':observed_at})
        key = 'settle-' + digest({'edition':edition, 'settlement_id':settlement['settlement_id']})
        cached = store.get(race_id, 'settlement', key)
        cache_hit = cached is not None
        if cached:
            existing = cached['payload']
            if existing['forecast_sha256'] != forecast['content_sha256'] or existing['result_sha256'] != settlement['result_sha256']:
                raise ValueError('BLOCKED_SETTLEMENT_CACHE_BINDING')
            settlement = existing
        else:
            settlement.update(edition=edition, edition_type=publication.get('edition_type', publication.get('edition_kind', 'PRE_DAY')),
                              bundle_hash=digest(bundle), publication_hash=digest(publication),
                              base_edition=publication.get('base_edition'), base_bundle_hash=publication.get('base_bundle_hash'),
                              official_settlements=0 if synthetic else 1, training_executed=False,
                              source_result_hash=digest(result), result_revision=result.get('revision', 1))
            store.save(race_id, 'result', digest(result), result)
            store.save(race_id, 'settlement-forecast', edition, forecast)
            cached = store.save(race_id, 'settlement', key, settlement)
        outcome = _outcome(bundle, result)
        reviews, candidates = [], []
        for summary in settlement['summary']:
            author = summary['forecaster_id']
            final = bundle['final'][author]
            author_key = 'review-' + digest({'edition':edition, 'settlement_id':settlement['settlement_id'], 'forecaster_id':author})
            review = {'schema':'prism.ops.review/v1', 'race_id':race_id, 'edition':edition,
                      'forecaster_id':author, 'settlement_id':settlement['settlement_id'],
                      'bundle_hash':digest(bundle), 'result_sha256':settlement['result_sha256'],
                      'initial_picks':bundle['preliminary'].get(author, {}).get('picks', []),
                      'final_picks':final['picks'], 'change_reason':final.get('change_reason'),
                      'performance':summary, 'official_outcome':outcome,
                      'ai_probability_metrics':'UNAVAILABLE_NO_AI_PROBABILITY_OUTPUT',
                      'ai_reflection_execution':'NOT_EXECUTED', 'status':'REVIEW_RECORDED_NOT_TRAINED',
                      'execution_mode':'SYNTHETIC' if synthetic else 'COMPUTED_FROM_OFFICIAL_RESULT',
                      'recorded_at':cached['persisted_at']}
            candidate = {'schema':'prism.ops.learning_candidate/v1', 'race_id':race_id, 'edition':edition,
                         'forecaster_id':author, 'review_hash':digest(review), 'settlement_id':settlement['settlement_id'],
                         'status':'CANDIDATE_SHADOW_REQUIRED', 'training_executed':False, 'adopted':False,
                         'eligible_for_automatic_adoption':False,
                         'next_action':'Review evidence, counterarguments and missing observations before proposing a testable change',
                         'available_after':cached['persisted_at'], 'execution_mode':review['execution_mode']}
            store.save(race_id, 'review', author_key, review)
            store.save(race_id, 'learning-candidate', author_key, candidate)
            reviews.append(review); candidates.append(candidate)
        store.status(race_id, 'EXECUTED', {'stage':'POST_REVIEW', 'edition':edition,
                     'settlement_id':settlement['settlement_id'], 'official_settlements':0 if synthetic else 1,
                     'training_executed':False, 'production_deployed':False})
        return {'settlement':settlement, 'reviews':reviews, 'learning_candidates':candidates,
                'artifact':cached, 'official_settlements':0 if synthetic or cache_hit else 1,
                'saved_official_settlements':0 if synthetic else 1, 'cache_hit':cache_hit}


def settle_saved(store, race_id, result, *, edition='pre-v1', now=utcnow):
    return _settle_saved(store, race_id, result, edition=edition, now=now, synthetic=False)


def settle_synthetic_saved(store, race_id, result, *, edition='pre-v1', now=utcnow):
    """Explicit software-fixture path; never increments official success counts."""
    return _settle_saved(store, race_id, result, edition=edition, now=now, synthetic=True)


def reflect_saved(store, race_id, provider, *, edition='pre-v1', now=utcnow):
    """Call each actual AI after official settlement; failure never erases it.

    The retained reflection is an opinion about a known result. It cannot become
    a PRE prediction, adopted model update or a claimed executed Shadow trial.
    """
    from .characters import get_character, verify_character_snapshot
    store.safe(race_id); store.safe(edition)
    with store.lock(race_id):
        observed_at = now()
        publication, bundle, _ = _validate_saved(store, race_id, edition, observed_at)
        settlements = []
        for key, persisted_at in store.db.execute("SELECT key,persisted_at FROM artifacts WHERE race_id=? AND kind='settlement'", (race_id,)):
            saved = store.get(race_id, 'settlement', key)
            candidate = saved['payload']
            if candidate.get('edition') == edition and candidate.get('official_settlements') == 1:
                settlements.append((candidate.get('result_revision', 1), timestamp(persisted_at), key, saved))
        if not settlements:
            raise ValueError('BLOCKED_OFFICIAL_SETTLEMENT_REQUIRED_FOR_REFLECTION')
        settlement_artifact = sorted(settlements, key=lambda item:item[:3])[-1][3]
        settlement = settlement_artifact['payload']
        if settlement['bundle_hash'] != digest(bundle):
            raise ValueError('BLOCKED_REFLECTION_SETTLEMENT_BINDING')
        result_artifact = _get(store, race_id, 'result', settlement['source_result_hash'])
        result = result_artifact['payload']
        snapshot_entry = store.get(race_id, 'characters', edition)
        if snapshot_entry is None and publication.get('base_edition'):
            snapshot_entry = store.get(race_id, 'characters', publication['base_edition'])
        if snapshot_entry is None:
            raise ValueError('BLOCKED_REFLECTION_CHARACTER_SNAPSHOT_MISSING')
        snapshot = snapshot_entry['payload']
        verify_character_snapshot(snapshot)
        if snapshot['snapshot_hash'] != bundle['race']['character_snapshot_hash']:
            raise ValueError('BLOCKED_REFLECTION_CHARACTER_SNAPSHOT_CHANGED')
        available_at = max(timestamp(result_artifact['persisted_at']), timestamp(settlement_artifact['persisted_at']))
        if available_at > timestamp(observed_at):
            raise ValueError('BLOCKED_POST_EVIDENCE_NOT_YET_AVAILABLE')
        source_refs = [result['official_source'], result_artifact['path'], settlement_artifact['path'],
                       'original_final', 'core_prediction']
        completed, blocked = [], []
        for summary in settlement['summary']:
            author = summary['forecaster_id']
            key = 'reflect-' + digest({'edition':edition, 'settlement_id':settlement['settlement_id'], 'forecaster_id':author})
            character = get_character(snapshot, author)
            context = {'race_id':race_id, 'phase':'POST_REVIEW', 'runners':bundle['race']['runners'],
                       'character_snapshot_hash':snapshot['snapshot_hash'], 'original_final':bundle['final'][author],
                       'official_settlement':settlement, 'forecaster_performance':summary,
                       'official_result':result, 'core_prediction':bundle.get('core_prediction'),
                       'source_refs':source_refs, 'source_evidence_available_at':available_at.isoformat(),
                       'scope':'POST reflection only; no revision of PRE history and no learning adoption'}
            try:
                saved = store.get(race_id, 'ai-review', key)
                if saved is None:
                    execution = provider.predict(context, character, stage='RESPONSE')
                    validate_execution(execution, context=context, character=character, require_independent=True)
                    if not set(execution['output']['evidence_refs']) <= set(source_refs):
                        raise ValueError('POST_REFLECTION_EVIDENCE_REFERENCES_UNBOUND')
                    if timestamp(execution['receipt']['started_at']) < available_at:
                        raise ValueError('POST_REFLECTION_PRECEDES_RESULT')
                    saved = store.save(race_id, 'ai-review', key, execution)
                execution = deepcopy(saved['payload'])
                execution['persisted_at'] = saved['persisted_at']
                validate_execution(execution, context=context, character=character, require_independent=True)
                if not set(execution['output']['evidence_refs']) <= set(source_refs):
                    raise ValueError('POST_REFLECTION_EVIDENCE_REFERENCES_UNBOUND')
                if timestamp(execution['receipt']['started_at']) < available_at:
                    raise ValueError('POST_REFLECTION_PRECEDES_RESULT')
                if timestamp(execution['persisted_at']) < timestamp(execution['receipt']['completed_at']):
                    raise ValueError('POST_REFLECTION_SAVE_TIME_REJECTED')
                candidate = {'schema':'prism.ops.reflection_candidate/v1', 'race_id':race_id, 'edition':edition,
                             'forecaster_id':author, 'settlement_id':settlement['settlement_id'],
                             'reflection_hash':saved['content_hash'], 'reflection_execution_id':execution['receipt']['execution_id'],
                             'available_after':saved['persisted_at'], 'status':'CANDIDATE_SHADOW_REQUIRED',
                             'shadow_executed':False, 'training_executed':False, 'adopted':False,
                             'next_context_policy':'AS_OF_FILTER_REQUIRED_BEFORE_REUSE'}
                store.save(race_id, 'learning-candidate', key, candidate)
                completed.append({'forecaster_id':author, 'execution_id':execution['receipt']['execution_id'],
                                  'reflection_hash':saved['content_hash'], 'persisted_at':saved['persisted_at']})
            except Exception as exc:
                # Do not persist a successful reflection or roll back settlement.
                blocked.append({'forecaster_id':author, 'status':'NOT_EXECUTED',
                                'reason':type(exc).__name__ + ': ' + str(exc)[:300]})
        report = {'schema':'prism.ops.post_reflection/v1', 'race_id':race_id, 'edition':edition,
                  'settlement_id':settlement['settlement_id'], 'completed':completed, 'blocked':blocked,
                  'independent_reflections':len(completed), 'training_executed':False, 'shadow_executed':False,
                  'adopted':False, 'official_settlement_preserved':True}
        store.save(race_id, 'reflection-report', 'reflection-' + digest({'edition':edition,'report':report}), report)
        store.status(race_id, 'BLOCKED_POST_REFLECTION' if blocked else 'EXECUTED',
                     {'stage':'POST_REFLECTION','edition':edition,'independent_reflections':len(completed),
                      'blocked':blocked,'official_settlements':1,'training_executed':False})
        return report
