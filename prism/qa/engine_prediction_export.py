"""Fail-closed export of experimental engine predictions to PRISM adapter input.

Only an upstream verified source may be promoted to a live pre-race edition.
The engine currently emits source_authenticity_verified=False, so this bridge
intentionally rejects unverified live output rather than fabricating proof.
"""
from datetime import datetime

def _time(value):
    if not isinstance(value, str):
        raise ValueError('invalid_timestamp')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timezone_required')
    return dt

def export_engine_predictions(artifact, *, horses, predictor_id, source, saved_at, version, scheduled_start_at):
    if artifact.get('schema') != 'prism.engine.prediction/v1':
        raise ValueError('invalid_engine_schema')
    if artifact.get('mode') != 'PRE_AVAILABLE':
        raise ValueError('non_live_engine_mode')
    if artifact.get('source_authenticity_verified') is not True:
        raise ValueError('unverified_engine_source')
    if not isinstance(predictor_id, str) or not predictor_id.strip():
        raise ValueError('missing_predictor_id')
    if not isinstance(source, str) or not source.strip():
        raise ValueError('missing_source')
    if not isinstance(version, str) or not version.strip():
        raise ValueError('missing_version')
    if not isinstance(artifact.get('race_id'), str) or not artifact['race_id']:
        raise ValueError('missing_race_id')
    if not isinstance(horses, dict) or not horses:
        raise ValueError('missing_horse_registry')
    lock = _time(artifact.get('locked_at'))
    saved = _time(saved_at)
    start = _time(scheduled_start_at)
    if lock > saved or saved >= start:
        raise ValueError('invalid_pre_race_timeline')
    if _time(artifact.get('cutoff')) < lock:
        raise ValueError('engine_lock_after_cutoff')
    win = artifact.get('win')
    if not isinstance(win, dict) or set(win) != set(horses):
        raise ValueError('horse_id_mismatch')
    if any(not isinstance(v, str) or not v.strip() for v in horses.values()) or len(set(horses.values())) != len(horses):
        raise ValueError('ambiguous_horse_names')
    return {
        'race_id': artifact['race_id'], 'scheduled_start_at': scheduled_start_at,
        'saved_at': saved_at, 'version': version, 'source': source,
        'predictions': [
            {'horse_name': horses[k], 'predictor_id': predictor_id,
             'selection': {'win_probability': win[k]}}
            for k in sorted(win)
        ]
    }
