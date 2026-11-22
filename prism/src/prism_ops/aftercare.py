"""Poll official results for saved publications and resume POST processing.

Repeated identical source bytes reuse the first observed snapshot. Locally
observed corrections append new result/settlement versions; no PRE artifact or
older result is overwritten. Injected/synthetic sources never count as official.
"""
from copy import deepcopy
from datetime import date
from urllib.error import HTTPError

from prism_engine.contracts import digest, timestamp
from . import official
from .postrace import settle_saved, reflect_saved, _node
from .store import utcnow


def _expectations(job):
    required = {'race_id','result_url','authority','expected_date','expected_venue','expected_race_no'}
    if not isinstance(job, dict) or not required <= set(job):
        raise ValueError('settlement job requires race_id/result_url/authority/expected_date/expected_venue/expected_race_no')
    if job['authority'] not in {'JRA','NAR'}:
        raise ValueError('settlement job authority must be JRA or NAR')
    date.fromisoformat(job['expected_date'])
    if type(job['expected_race_no']) is not int or not 1 <= job['expected_race_no'] <= 12:
        raise ValueError('settlement job race number must be an integer in 1..12')
    if not isinstance(job['expected_venue'], (str, int)) or isinstance(job['expected_venue'], bool):
        raise ValueError('settlement job venue required')
    if type(job.get('reflect', False)) is not bool:
        raise ValueError('reflect must be a boolean')
    official.validate_official_url(job['result_url'], job['authority'])
    return {'authority':job['authority'], 'expected_date':job['expected_date'],
            'expected_venue':job['expected_venue'], 'expected_race_no':job['expected_race_no'],
            'expected_race_name':job.get('expected_race_name')}


def _parse(source, expected):
    kwargs = {key:expected[key] for key in ('expected_date','expected_venue','expected_race_no')}
    if expected['authority'] == 'JRA':
        return official.parse_jra_result(source, expected_race_name=expected['expected_race_name'], **kwargs)
    result = official.parse_nar_result(source, **kwargs)
    if expected['expected_race_name'] is not None and result.get('race_identity', {}).get('race_name') != expected['expected_race_name']:
        raise ValueError('official NAR result race title mismatch')
    return result


def _semantic_result(result):
    # Observation time/HTML formatting changes do not create new performance.
    def normalized(items):
        rows=[]
        for value in items:
            row=deepcopy(value)
            kind=row.get('type')
            field='frame_nos' if kind in {'FRAME','FRAME_QUINELLA'} else 'horse_nos'
            if kind in {'WIN','PLACE','QUINELLA','WIDE','TRIO','FRAME','FRAME_QUINELLA'} and field in row:
                row[field]=sorted(row[field])
            if kind == 'FRAME_QUINELLA':
                row['type']='FRAME'
            rows.append(row)
        return sorted(rows,key=digest)
    return digest({'race_id':result['race_id'],'status':result.get('status'),
                   'payouts':normalized(result['payouts']), 'refunds':normalized(result.get('refunds',[])),
                   'complete_payouts':result.get('complete_payouts'),
                   'complete_bet_types':sorted('FRAME' if t=='FRAME_QUINELLA' else t for t in result.get('complete_bet_types',[])),
                   'refunded_bet_types':sorted(result.get('refunded_bet_types',[]))})


def _cached_result(store, race_id, edition, source, result, expected):
    scope=digest({'edition':edition,'expected':expected})
    source_key=digest({'scope':scope,'source_sha256':source['source_sha256']})
    cached=store.get(race_id,'aftercare-source',source_key)
    if cached:
        payload=cached['payload']
        if payload['scope'] != scope or payload['source']['source_sha256'] != source['source_sha256']:
            raise ValueError('CACHED_RESULT_SOURCE_BINDING_MISMATCH')
        return payload['result'], True
    semantic_hash=_semantic_result(result)
    versions=[]
    for key, in store.db.execute("SELECT key FROM artifacts WHERE race_id=? AND kind='aftercare-result'",(race_id,)):
        artifact=store.get(race_id,'aftercare-result',key)
        if artifact['payload']['scope'] == scope:
            versions.append(artifact['payload'])
    previous=max(versions,key=lambda row:row['local_revision']) if versions else None
    if previous and previous['semantic_hash'] == semantic_hash:
        result=previous['result']
        reused=True
    else:
        result=deepcopy(result)
        result['revision']=1 if previous is None else previous['local_revision']+1
        result['revision_origin']='LOCAL_OBSERVATION_SEQUENCE_NOT_OFFICIAL_REVISION'
        if previous is not None:
            result['correction_of']=previous['result']['source_snapshot']['normalized_sha256']
        result['source_snapshot']['parser_normalized_sha256']=result['source_snapshot']['normalized_sha256']
        result['source_snapshot']['normalized_sha256']=_node({'operation':'result_digest','result':result})['normalized_sha256']
        local_revision=result['revision']
        store.save(race_id,'aftercare-result',digest({'scope':scope,'local_revision':local_revision}),
                   {'scope':scope,'edition':edition,'local_revision':local_revision,
                    'semantic_hash':semantic_hash,'result':result})
        reused=False
    store.save(race_id,'aftercare-source',source_key,
               {'scope':scope,'source':source,'result':result,'first_result_reused':reused})
    return result, reused


def _existing_settlement(store, race_id, edition, result):
    source_hash=digest(result)
    for key, in store.db.execute("SELECT key FROM artifacts WHERE race_id=? AND kind='settlement'",(race_id,)):
        artifact=store.get(race_id,'settlement',key)
        payload=artifact['payload']
        if payload.get('edition') == edition and payload.get('source_result_hash') == source_hash and payload.get('official_settlements') == 1:
            return payload
    return None


def process_settlement_job(job, store, provider=None, *, now=utcnow):
    """One repeatable poll. Counts report newly persisted official settlements.

    ``saved_official_settlements`` states whether this result has already been
    settled; retries return ``official_settlements=0`` rather than inflate counts.
    A reflection failure retains the independently saved calculation and result.
    """
    race_id=job.get('race_id') if isinstance(job,dict) else None
    edition=job.get('edition','pre-v1') if isinstance(job,dict) else 'pre-v1'
    base={'race_id':race_id,'edition':edition,'official_settlements':0,'saved_official_settlements':0}
    try:
        expected=_expectations(job)
        store.safe(race_id);store.safe(edition)
        publication=store.get(race_id,'publication',edition)
        bundle=store.get(race_id,'bundle',edition)
        if not publication or not bundle or publication['payload'].get('gate',{}).get('ready') is not True:
            return {**base,'status':'PENDING_PUBLICATION','reason':'accepted saved publication and bundle required'}
        if publication['payload'].get('bundle_hash') != bundle['content_hash']:
            raise ValueError('PUBLICATION_BUNDLE_BINDING_MISMATCH')
        race=bundle['payload']['race']
        if race['race_id'] != race_id or race.get('authority') != expected['authority']:
            raise ValueError('SETTLEMENT_JOB_RACE_OR_AUTHORITY_MISMATCH')
        observed=now()
        if timestamp(observed) < timestamp(race['start_at']):
            return {**base,'status':'NOT_DUE','reason':'official settlement waits until scheduled off'}
        source=official.fetch_official_snapshot(job['result_url'],store.directory/'official-results'/race_id)
        if source.get('mode') != 'LIVE_FETCH':
            raise ValueError('SYNTHETIC_RESULT_SOURCE_CANNOT_BECOME_OFFICIAL_SETTLEMENT')
        if timestamp(source['captured_at']) > timestamp(now()):
            raise ValueError('RESULT_SOURCE_CAPTURED_IN_FUTURE')
        result=_parse(source,expected)
        if result['race_id'] != race_id or result.get('mode') != 'OFFICIAL':
            raise ValueError('OFFICIAL_RESULT_IDENTITY_OR_EXECUTION_MODE_MISMATCH')
        # Serialize local result-version assignment, then release before the
        # settlement service takes the same race lock.
        with store.lock(race_id):
            result,reused=_cached_result(store,race_id,edition,source,result,expected)
        existing=_existing_settlement(store,race_id,edition,result)
        response=settle_saved(store,race_id,result,edition=edition,now=now)
        settlement=response['settlement']
        report={**base,'status':'SKIPPED_SETTLED' if existing or response.get('cache_hit') else 'SETTLED',
                'official_settlements':0 if existing else response['official_settlements'],
                'saved_official_settlements':1,'settlement_id':settlement['settlement_id'],
                'result_source_reused':reused,'result_revision':result.get('revision',1),
                'reflection_status':'NOT_REQUESTED'}
        if job.get('reflect'):
            try:
                if provider is None:
                    from .provider import OpenAIProvider
                    provider=OpenAIProvider()
                reflection=reflect_saved(store,race_id,provider,edition=edition,now=now)
                report['reflection']=reflection
                report['reflection_status']='BLOCKED' if reflection['blocked'] else 'EXECUTED'
                if reflection['blocked']:
                    report['status']='SETTLED_REFLECTION_BLOCKED'
            except Exception as exc:
                report.update(status='SETTLED_REFLECTION_BLOCKED',reflection_status='BLOCKED',
                              reflection_reason=type(exc).__name__+': '+str(exc)[:300])
        return report
    except Exception as exc:
        reason=type(exc).__name__+': '+str(exc)[:300]
        pending=(isinstance(exc,HTTPError) and exc.code==404 or
                 isinstance(exc,official.OfficialSourceError) and
                 any(text in str(exc) for text in ('not published','not available','final JRA finish and payout tables required')))
        return {**base,'status':'PENDING_RESULT' if pending else 'BLOCKED','reason':reason,
                'reflection_status':'NOT_EXECUTED'}
