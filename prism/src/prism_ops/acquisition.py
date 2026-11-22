"""Watch explicit official race URLs and freeze resumable prediction jobs.

Source-byte hashes select the original capture, so polling an unchanged page
does not create new editions from a changed retrieval timestamp. All supplied
test fetchers/parsers are forced to SYNTHETIC and cannot verify official input.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

from prism_engine.contracts import digest, timestamp
from . import official
from .store import Store, utcnow


def _load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _job_options(job, watch, captured_at):
    # Timing and rendering are worker options, not new predictive evidence.
    # Changing them must neither reuse stale options nor rerun unchanged models.
    return {**job, 'due_at':watch.get('not_before',captured_at),
            'render':watch.get('render',True)}


def prepare_watch(watch, store, *, now=utcnow, fetcher=None, parser=None):
    """Return a frozen runtime job, or a NOT_DUE result before ``not_before``.

    ``evidence`` is a JSON mapping keyed by canonical horse_id, carrying the
    source-backed entries accepted by ``assemble_engine_input``. No evidence is
    created from a racecard alone. Injected callables are tests, never LIVE_FETCH.
    """
    required={'race_id','authority','official_url','expected_date','expected_venue',
              'expected_race_no','characters','evidence','engine_parameters'}
    if not isinstance(watch,dict) or not required<=set(watch):
        raise ValueError('watch requires explicit official identity, characters, evidence and engine_parameters')
    race_id=Store.safe(watch['race_id'])
    try:
        authority=watch['authority']
        if authority not in {'JRA','NAR'}:
            raise ValueError('unsupported watch authority')
        official.validate_official_url(watch['official_url'],authority)
        if watch.get('not_before') and timestamp(now())<timestamp(watch['not_before']):
            return {'race_id':race_id,'status':'NOT_DUE','not_before':watch['not_before']}
        parameters=watch['engine_parameters']
        expected_parameters={'venue','surface','distance_m','direction','class_rating','barrier_count'}
        if not isinstance(parameters,dict) or set(parameters)!=expected_parameters:
            raise ValueError('explicit engine course parameters required')
        if authority=='JRA' and not watch.get('expected_race_name'):
            raise ValueError('explicit JRA expected_race_name required')
        synthetic=fetcher is not None or parser is not None
        fetch=fetcher or official.fetch_official_snapshot
        parse=parser or (official.parse_jra_racecard if authority=='JRA' else official.parse_nar_racecard)
        # Acquisition shares the per-race lock with execution and publication.
        with store.lock(race_id):
            snapshot=deepcopy(fetch(watch['official_url'],store.directory/'sources'/race_id))
            if synthetic:
                snapshot['mode']='SYNTHETIC'
                snapshot['identity_verified']=False
            if snapshot.get('authority')!=authority:
                raise ValueError('official snapshot authority mismatch')
            source_hash=snapshot.get('source_sha256')
            if (not isinstance(source_hash,str) or len(source_hash)!=64 or
                    any(c not in '0123456789abcdef' for c in source_hash)):
                raise ValueError('source bytes hash required')
            identity={k:watch[k] for k in ('race_id','authority','expected_date','expected_venue','expected_race_no')}
            identity['expected_race_name']=watch.get('expected_race_name')
            identity['official_url']=watch['official_url']
            card_key=digest({'source_sha256':source_hash,'identity':identity,
                             'mode':'SYNTHETIC' if synthetic else snapshot.get('mode')})
            frozen_card=store.get(race_id,'watch-card',card_key)
            if frozen_card is None:
                kwargs={k:watch[k] for k in ('expected_date','expected_venue','expected_race_no')}
                if authority=='JRA':kwargs['expected_race_name']=watch['expected_race_name']
                card=deepcopy(parse(snapshot,**kwargs))
                if card.get('race_id')!=race_id or card.get('authority')!=authority:
                    raise ValueError('watch and official race identity mismatch')
                if synthetic:
                    card.update(mode='SYNTHETIC',source_verified=False)
                    if isinstance(card.get('source_evidence'),dict):
                        card['source_evidence']['mode']='SYNTHETIC'
                elif snapshot.get('mode')!='LIVE_FETCH' or card.get('source_verified') is not True:
                    raise ValueError('BLOCKED_OFFICIAL_IDENTITY')
                frozen_card=store.save(race_id,'watch-card',card_key,card)
            card=frozen_card['payload']
            stage=card.get('declaration_stage')
            if stage not in {'ENTRIES_CONFIRMED','DRAW_CONFIRMED'}:
                raise ValueError('official declaration stage required')
            try:
                evidence=_load(watch['evidence'])
            except (OSError,ValueError,TypeError) as exc:
                raise ValueError('BLOCKED_SOURCE_EVIDENCE: readable horse evidence file required') from exc
            characters=_load(watch['characters'])
            input_key=digest({'card_hash':frozen_card['content_hash'],
                              'evidence_hash':digest(evidence),'characters_hash':digest(characters),
                              'engine_parameters':parameters})
            edition=('pre-entries-' if stage=='ENTRIES_CONFIRMED' else 'pre-draw-')+source_hash[:16]+'-'+input_key[:12]
            cached=store.get(race_id,'watch-inputs',input_key)
            if cached is not None:
                return _job_options(cached['payload'],watch,card['captured_at'])
            # This is the existing official/evidence boundary, not a second
            # feature generator. Keep it available to both scripts and workers.
            scripts=str(Path(__file__).resolve().parents[2]/'scripts')
            if scripts not in sys.path:sys.path.insert(0,scripts)
            from assemble_official_engine_input import assemble_engine_input
            try:
                raw,_=assemble_engine_input(card,evidence,locked_at=now(),**parameters)
            except (KeyError,ValueError,TypeError) as exc:
                raise ValueError('BLOCKED_SOURCE_EVIDENCE: '+str(exc)) from exc
            raw_entry=store.save(race_id,'watch-engine',input_key,raw)
            character_entry=store.save(race_id,'watch-characters',digest(characters),characters)
            job={'race_id':race_id,'card':frozen_card['path'],'characters':character_entry['path'],
                 'engine_input':raw_entry['path'],'edition':edition,
                 'due_at':watch.get('not_before',card['captured_at']),
                 'render':watch.get('render',True),'acquisition_mode':raw['mode'],
                 'source_sha256':source_hash,'declaration_stage':stage,
                 'official_fetch_executed':not synthetic}
            return store.save(race_id,'watch-inputs',input_key,job)['payload']
    except Exception as exc:
        store.status(race_id,'BLOCKED',{'reason':type(exc).__name__+': '+str(exc)[:300],
                                      'official_publications':0})
        raise
