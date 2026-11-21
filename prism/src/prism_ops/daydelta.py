"""Immutable race-day corrections based on an already published preceding day.

Source bytes and provider transcripts are retained. Synthetic corrections remain
candidates and cannot become official publications. The base ability lock and
the preceding-day newspaper are never overwritten.
"""
from copy import deepcopy
from hashlib import sha256
from math import isfinite
from pathlib import Path
from zoneinfo import ZoneInfo

from prism_engine.contracts import digest, timestamp
from prism_pre_day_gate import DAY_DELTA_FIELDS, check_publication
from .characters import get_character, verify_character_snapshot
from .provider import validate_execution
from .store import utcnow

JST = ZoneInfo('Asia/Tokyo')
POST_FIELDS = {'result', 'results', 'official_result', 'settlement', 'payouts', 'winners',
               'winner', 'finish_position', 'win_payouts', 'refund_keys', 'target_result'}


def _no_results(value):
    if isinstance(value, dict):
        if set(value) & POST_FIELDS or value.get('phase') == 'POST':
            raise ValueError('POST_RESULT_REJECTED_FROM_DAY_CORRECTION')
        for child in value.values():
            _no_results(child)
    elif isinstance(value, list):
        for child in value:
            _no_results(child)


def _base(store, race_id, edition, *, checked_at=None):
    publication = store.get(race_id, 'publication', edition)
    bundle = store.get(race_id, 'bundle', edition)
    characters = store.get(race_id, 'characters', edition)
    if not publication or not bundle or not characters:
        raise ValueError('PUBLISHED_PRECEDING_DAY_BASE_REQUIRED')
    if (publication['payload'].get('gate', {}).get('ready') is not True or
            publication['payload'].get('bundle_hash') != bundle['content_hash']):
        raise ValueError('BASE_PUBLICATION_BINDING_REJECTED')
    verify_character_snapshot(characters['payload'])
    if bundle['payload']['race'].get('character_snapshot_hash') != characters['payload']['snapshot_hash']:
        raise ValueError('BASE_CHARACTER_SNAPSHOT_MISMATCH')
    race = bundle['payload']['race']
    published = timestamp(publication['payload']['published_at'])
    persisted = timestamp(publication['persisted_at'])
    checked = timestamp(checked_at or utcnow())
    if (not published <= persisted <= checked or
            persisted.astimezone(JST).date() >= timestamp(race['start_at']).astimezone(JST).date() or
            timestamp(bundle['persisted_at']) > persisted or timestamp(characters['persisted_at']) > persisted):
        raise ValueError('BASE_PUBLICATION_NOT_DURABLY_SAVED_ON_PRECEDING_DAY')
    receipts = store.get(race_id, 'receipts', edition)
    report = check_publication(race, bundle['payload']['preliminary'], bundle['payload']['discussions'],
                bundle['payload']['final'], publication['payload']['published_at'],
                execution_receipts=receipts['payload'] if receipts else {},
                paper=publication['payload'].get('paper'), publication_content_hash=bundle['content_hash'],
                checked_at=checked.isoformat())
    if not report['ready']:
        raise ValueError('BASE_PUBLICATION_RECHECK_FAILED:' + ','.join(report['errors']))
    return publication, bundle, characters['payload']


def _before_off(race, observed_at):
    observed, start = timestamp(observed_at), timestamp(race['start_at'])
    if observed.astimezone(JST).date() != start.astimezone(JST).date() or observed >= start:
        raise ValueError('DAY_CORRECTION_REQUIRES_RACE_DAY_BEFORE_OFF')
    return observed


def _changes(changes, runners):
    if not isinstance(changes, dict) or set(changes) - DAY_DELTA_FIELDS:
        raise ValueError('ONLY_ALLOWED_DAY_DELTA_FIELDS_ACCEPTED')
    _no_results(changes)
    ids = {r['horse_id'] for r in runners}
    for key, value in changes.items():
        if value is None or value == {} or value == [] or value == '':
            raise ValueError('EMPTY_DAY_DELTA_FIELD:' + key)
        if key in {'body_weight', 'body_weight_change', 'rider_change'}:
            if not isinstance(value, dict) or not set(value) <= ids:
                raise ValueError('DAY_DELTA_REQUIRES_KNOWN_HORSE_IDS:' + key)
        if key in {'body_weight', 'body_weight_change'}:
            if any(type(n) not in (int, float) or not isfinite(n) or key == 'body_weight' and n <= 0 for n in value.values()):
                raise ValueError('DAY_WEIGHT_OBSERVATIONS_MUST_BE_FINITE:' + key)
        if key in {'going', 'weather'} and (not isinstance(value, str) or not value.strip()):
            raise ValueError('DAY_CONDITION_TEXT_REQUIRED:' + key)
        if key in {'odds', 'track_bias'} and not isinstance(value, (dict, str)):
            raise ValueError('STRUCTURED_OR_TEXT_DAY_OBSERVATION_REQUIRED:' + key)
        if key == 'rider_change' and any(
                not (isinstance(v, str) and v.strip()) and
                not (isinstance(v, dict) and isinstance(v.get('jockey_name'), str) and v['jockey_name'].strip())
                for v in value.values()):
            raise ValueError('RIDER_CHANGE_REQUIRES_EXPLICIT_NEW_RIDER')
        if key == 'scratches':
            if (not isinstance(value, list) or any(h not in ids for h in value) or
                    len(set(value)) != len(value) or len(value) == len(ids)):
                raise ValueError('INVALID_SCRATCHED_RUNNER_SET')
    digest(changes)


def _day_race(base_race, changes):
    race = deepcopy(base_race)
    scratched = set(changes.get('scratches', []))
    race['runners'] = [r for r in race['runners'] if r['horse_id'] not in scratched]
    race['scratched_runners'] = [dict(r, status='SCRATCHED') for r in base_race['runners'] if r['horse_id'] in scratched]
    race['day_conditions'] = deepcopy(changes)
    for runner in race['runners']:
        horse = runner['horse_id']
        for key in ('body_weight', 'body_weight_change'):
            if horse in changes.get(key, {}):
                runner[key] = changes[key][horse]
        if horse in changes.get('rider_change', {}):
            rider = changes['rider_change'][horse]
            runner['jockey_name'] = rider if isinstance(rider, str) else rider['jockey_name']
            if isinstance(rider, dict) and rider.get('jockey_id'):
                runner['jockey_id'] = rider['jockey_id']
            else:
                runner.pop('jockey_id', None)
    for field in ('going', 'weather', 'track_bias'):
        if field in changes:
            race[field] = deepcopy(changes[field])
    return race


def _day_context(base, race, snapshot, delta):
    return {'race_id': race['race_id'], 'race': race, 'runners': race['runners'],
            'character_snapshot_hash': snapshot['snapshot_hash'], 'core_prediction': deepcopy(base['core_prediction']),
            'base_final': deepcopy(base['final']), 'day_delta': delta,
            'source_refs': list(dict.fromkeys([*base['race'].get('source_refs', []), delta['source']['official_url']]))}


def _source(source, race_id, changes, as_of):
    from .official import validate_official_url
    if not isinstance(source, dict):
        raise ValueError('DAY_SOURCE_SNAPSHOT_REQUIRED')
    _no_results(source)
    if source.get('race_id') != race_id:
        raise ValueError('DAY_SOURCE_RACE_ID_MISMATCH')
    validate_official_url(source.get('official_url'))
    captured = timestamp(source['captured_at'])
    available = timestamp(source.get('available_at', source['captured_at']))
    if available > captured or captured > timestamp(as_of):
        raise ValueError('DAY_SOURCE_UNAVAILABLE_AT_CORRECTION')
    if captured.astimezone(JST).date() != timestamp(as_of).astimezone(JST).date():
        raise ValueError('DAY_SOURCE_MUST_BE_OBSERVED_ON_RACE_DAY')
    body = Path(source['body_path']).read_bytes()
    if sha256(body).hexdigest() != source.get('source_sha256'):
        raise ValueError('DAY_SOURCE_BYTES_CHANGED')
    if source.get('normalized_changes_hash', digest(changes)) != digest(changes):
        raise ValueError('DAY_SOURCE_CHANGES_BINDING_MISMATCH')
    if source.get('mode') not in {'LIVE_FETCH', 'SYNTHETIC'}:
        raise ValueError('EXPLICIT_DAY_SOURCE_MODE_REQUIRED')
    return {'snapshot': deepcopy(source), 'snapshot_hash': digest(source),
            'changes_hash': digest(changes), 'available_at': source.get('available_at', source['captured_at']),
            'captured_at': source['captured_at'], 'source_sha256': source['source_sha256'],
            'official_url': source['official_url'], 'source_semantic_reviewed': False}


def apply_day_delta(store, race_id, changes, change_reason, source_snapshot, provider, *,
                    version='day-v1', base_edition='pre-v1', now=utcnow):
    """Save a resumable correction candidate; render/review/publication is separate.

    ``source_snapshot`` is a retained official-source snapshot with explicit
    ``race_id``. Horse-specific changes use stable horse IDs; scratches list IDs.
    No field from POST result processing is accepted here.
    """
    store.safe(version); store.safe(base_edition)
    if version == base_edition:
        raise ValueError('DAY_VERSION_MUST_DIFFER_FROM_PRECEDING_DAY')
    with store.lock(race_id):
        try:
            publication, base_entry, snapshot = _base(store, race_id, base_edition, checked_at=now())
            base = base_entry['payload']
            _before_off(base['race'], now())
            _changes(changes, base['race']['runners'])
            if not changes:
                return {'race_id': race_id, 'status': 'SKIPPED_NO_CHANGES', 'base_bundle_hash': base_entry['content_hash']}
            if not isinstance(change_reason, str) or not change_reason.strip():
                raise ValueError('DAY_CORRECTION_REASON_REQUIRED')
            base_published = timestamp(publication['payload']['published_at'])
            if base_published.astimezone(JST).date() >= timestamp(base['race']['start_at']).astimezone(JST).date():
                raise ValueError('BASE_MUST_BE_PUBLISHED_ON_PRECEDING_DAY')
            source = _source(source_snapshot, race_id, changes, now())
            proposal = {'schema': 'prism.ops.day_delta/v1', 'race_id': race_id, 'version': version,
                        'base_edition': base_edition, 'base_bundle_hash': base_entry['content_hash'],
                        'base_publication_hash': publication['content_hash'], 'changes': deepcopy(changes),
                        'change_reason': change_reason.strip(), 'source': source,
                        'character_snapshot_hash': snapshot['snapshot_hash']}
            existing = store.get(race_id, 'day-delta', version)
            if existing:
                if {k: v for k, v in existing['payload'].items() if k != 'prepared_at'} != proposal:
                    raise ValueError('DAY_VERSION_CONFLICT_USE_NEW_VERSION')
                delta = existing['payload']
            else:
                delta = dict(proposal, prepared_at=now())
                store.save(race_id, 'day-delta', version, delta)
            published_day = store.get(race_id, 'publication', version)
            if published_day:
                saved_bundle = store.get(race_id, 'bundle', version)
                if (not saved_bundle or published_day['payload'].get('bundle_hash') != saved_bundle['content_hash'] or
                        saved_bundle['payload'].get('day_delta') != delta):
                    raise ValueError('DAY_PUBLICATION_BINDING_MISMATCH')
                return {'race_id': race_id, 'status': 'SKIPPED_PUBLISHED_DAY_CORRECTION',
                        'base_bundle_hash': base_entry['content_hash'], 'version': version}
            race = _day_race(base['race'], changes)
            # The original core probability/ability lock is carried verbatim.
            core = deepcopy(base['core_prediction'])
            context = _day_context(base, race, snapshot, delta)
            final, receipts = {}, {}
            for author in race['required_forecasters']:
                _before_off(race, now())
                key = version + '-final-' + author
                character = get_character(snapshot, author)
                cached = store.get(race_id, 'executions', key)
                if cached is None:
                    result = provider.predict(context, character, stage='FINAL')
                    validate_execution(result, context=context, character=character)
                    cached = store.save(race_id, 'executions', key, result)
                    # Retain an actually completed late call as evidence, but
                    # never continue it into a timely publication claim.
                    _before_off(race, now())
                result = deepcopy(cached['payload'])
                validate_execution(result, context=context, character=character)
                result['persisted_at'] = cached['persisted_at']
                eid = result['receipt']['execution_id']
                if eid in receipts:
                    raise ValueError('DUPLICATE_DAY_PROVIDER_EXECUTION')
                receipts[eid] = result
                final[author] = result['output']
            source_real = source_snapshot.get('mode') == 'LIVE_FETCH' and source_snapshot.get('identity_verified') is True
            independent = all(r['receipt']['execution_mode'] == 'INDEPENDENT_EXECUTION' for r in receipts.values())
            bundle = {'schema': 'prism.ops.publication_bundle/v1', 'race': race,
                      'mode': 'PRE_AVAILABLE' if source_real and independent else 'SYNTHETIC',
                      'edition_kind': 'DAY_CORRECTION', 'base_edition': base_edition,
                      'base_bundle_hash': base_entry['content_hash'], 'day_delta': delta,
                      'changes': deepcopy(changes), 'change_reason': change_reason.strip(),
                      'characters': deepcopy(snapshot['records']), 'core_prediction': core,
                      'preliminary': deepcopy(base['preliminary']), 'discussions': deepcopy(base['discussions']),
                      'base_final': deepcopy(base['final']), 'final': final,
                      'source_refs': context['source_refs']}
            store.save(race_id, 'bundle', version, bundle)
            store.save(race_id, 'receipts', version, receipts)
            store.save(race_id, 'characters', version, snapshot)
            if store.get(race_id, 'bundle', base_edition)['content_hash'] != base_entry['content_hash']:
                raise ValueError('PRECEDING_DAY_BASE_CHANGED')
            status = 'AWAITING_DAY_PAPER_QA' if source_real and independent else 'SYNTHETIC_DAY_CANDIDATE'
            store.status(race_id, status, {'version': version, 'base_edition': base_edition,
                         'base_bundle_hash': base_entry['content_hash'], 'official_publications_added': 0})
            return {'race_id': race_id, 'status': status, 'bundle': bundle,
                    'execution_receipts': receipts, 'paper': None,
                    'paper_out_dir': str(store.directory / 'papers' / race_id / version)}
        except Exception as exc:
            store.status(race_id, 'BLOCKED_DAY_CORRECTION', {'version': version, 'reason': type(exc).__name__ + ': ' + str(exc)[:300],
                                                          'official_publications_added': 0})
            raise


def render_day_delta(store, race_id, *, version='day-v1'):
    from .paper import render_operational_paper
    with store.lock(race_id):
        candidate = store.get(race_id, 'bundle', version)
        if not candidate or candidate['payload'].get('edition_kind') != 'DAY_CORRECTION':
            raise ValueError('DAY_CORRECTION_BUNDLE_REQUIRED')
        cached = store.get(race_id, 'paper', version)
        if cached:
            return cached['payload']
        manifest = render_operational_paper(candidate['payload'], store.directory / 'papers' / race_id / version, version=version)
        store.save(race_id, 'paper', version, manifest)
        return manifest


def check_day_publication(store, race_id, paper, *, version='day-v1', published_at, checked_at=None):
    """Read-only revalidation, including after racing, of the original publish time."""
    from prism_pre_day_gate import _paper
    errors = []
    try:
        entry = store.get(race_id, 'bundle', version)
        if entry is None:
            raise ValueError('DAY_CORRECTION_BUNDLE_REQUIRED')
        bundle = entry['payload']
        if bundle.get('edition_kind') != 'DAY_CORRECTION' or bundle.get('mode') != 'PRE_AVAILABLE':
            raise ValueError('OFFICIAL_DAY_CORRECTION_EXECUTION_REQUIRED')
        _before_off(bundle['race'], published_at)
        saved_publication = store.get(race_id, 'publication', version)
        if saved_publication and not (
                timestamp(published_at) <= timestamp(saved_publication['persisted_at']) < timestamp(bundle['race']['start_at']) and
                timestamp(saved_publication['persisted_at']) <= timestamp(checked_at or utcnow())):
            raise ValueError('DAY_PUBLICATION_DURABLE_TIMESTAMP_REJECTED')
        base_pub, base, snapshot = _base(store, race_id, bundle['base_edition'], checked_at=checked_at)
        if (base['content_hash'] != bundle['base_bundle_hash'] or
                digest(base['payload']['core_prediction']) != digest(bundle['core_prediction'])):
            raise ValueError('DAY_CORRECTION_BASE_OR_CORE_CHANGED')
        delta = store.get(race_id, 'day-delta', version)['payload']
        if (digest(delta) != digest(bundle['day_delta']) or delta['changes'] != bundle['changes'] or
                delta['change_reason'] != bundle['change_reason'] or
                delta['base_publication_hash'] != base_pub['content_hash'] or
                delta['base_bundle_hash'] != base['content_hash']):
            raise ValueError('DAY_DELTA_BINDING_MISMATCH')
        if not delta['changes'] or not isinstance(delta['change_reason'], str) or not delta['change_reason'].strip():
            raise ValueError('DAY_CORRECTION_CHANGES_AND_REASON_REQUIRED')
        _changes(delta['changes'], base['payload']['race']['runners'])
        if bundle['race'] != _day_race(base['payload']['race'], delta['changes']):
            raise ValueError('DAY_RACE_CHANGED_OUTSIDE_ALLOWED_DELTA')
        if _source(delta['source']['snapshot'], race_id, delta['changes'], published_at) != delta['source']:
            raise ValueError('DAY_SOURCE_SNAPSHOT_BINDING_MISMATCH')
        if delta['source']['snapshot'].get('mode') != 'LIVE_FETCH' or delta['source']['snapshot'].get('identity_verified') is not True:
            raise ValueError('DAY_SOURCE_IDENTITY_UNVERIFIED')
        receipts = store.get(race_id, 'receipts', version)['payload']
        if set(bundle['final']) != set(base['payload']['race']['required_forecasters']):
            raise ValueError('DAY_FORECASTER_COVERAGE_MISSING')
        latest = timestamp(delta['prepared_at'])
        expected_context = _day_context(base['payload'], bundle['race'], snapshot, delta)
        ids = set()
        for author, record in bundle['final'].items():
            result = receipts[record['execution_id']]
            validate_execution(result, context=expected_context, character=get_character(snapshot, author), require_independent=True)
            if (result['output'] != record or record['forecaster_id'] != author or
                    record['character_snapshot_hash'] != snapshot['snapshot_hash'] or
                    record['stage'] != 'FINAL' or record['race_id'] != race_id or
                    result['context']['day_delta'] != delta or
                    result['context']['base_final'] != base['payload']['final'] or
                    result['context']['core_prediction'] != base['payload']['core_prediction'] or
                    record['execution_id'] in ids):
                raise ValueError('DAY_EXECUTION_BINDING_MISMATCH')
            ids.add(record['execution_id'])
            saved, persisted = timestamp(record['saved_at']), timestamp(result['persisted_at'])
            started = timestamp(result['receipt']['started_at'])
            if not timestamp(delta['source']['captured_at']) <= timestamp(delta['prepared_at']) <= started <= saved <= persisted <= timestamp(published_at):
                raise ValueError('DAY_EXECUTION_TIME_MISMATCH')
            latest = max(latest, persisted)
        _paper(paper, race_id, entry['content_hash'], latest, timestamp(published_at), timestamp(checked_at or utcnow()), errors)
    except (KeyError, TypeError, ValueError, OSError, AttributeError) as exc:
        errors.append(str(exc))
    return {'ready': not errors, 'errors': errors, 'race_id': race_id, 'version': version,
            'published_at': published_at, 'edition_kind': 'DAY_CORRECTION'}


def publish_day_delta(store, race_id, paper, *, version='day-v1', now=utcnow):
    """Race-day gate: retain the base and require independent corrections + PDF QA."""
    with store.lock(race_id):
        existing = store.get(race_id, 'publication', version)
        if existing:
            entry = store.get(race_id, 'bundle', version)
            if (not entry or existing['payload'].get('paper') != paper or
                    existing['payload'].get('bundle_hash') != entry['content_hash']):
                raise ValueError('PUBLISHED_DAY_EDITION_IS_IMMUTABLE')
            return dict(check_day_publication(store, race_id, paper, version=version,
                        published_at=existing['payload']['published_at'], checked_at=now()), already_published=True)
        published_at = now()
        report = check_day_publication(store, race_id, paper, version=version,
                                       published_at=published_at, checked_at=now())
        store.save(race_id, 'publication-check', version + '-' + digest(report)[:12], report)
        if report['ready']:
            entry = store.get(race_id, 'bundle', version)
            bundle = entry['payload']
            saved = store.save(race_id, 'publication', version, {'bundle_hash': entry['content_hash'], 'paper': paper,
                       'published_at': published_at, 'base_edition': bundle['base_edition'],
                       'base_bundle_hash': bundle['base_bundle_hash'], 'edition_kind': 'DAY_CORRECTION', 'gate': report})
            if timestamp(saved['persisted_at']) >= timestamp(bundle['race']['start_at']):
                report = dict(report, ready=False, errors=['DAY_PUBLICATION_DURABLY_SAVED_AFTER_OFF'])
                store.save(race_id, 'publication-check', version + '-late-' + digest(report)[:12], report)
                store.status(race_id, 'BLOCKED_DAY_PUBLICATION', report)
                return report
            store.status(race_id, 'VERIFIED_DAY_CORRECTION', {'version': version, 'production_deployed': False})
        else:
            store.status(race_id, 'BLOCKED_DAY_PUBLICATION', report)
        return report
