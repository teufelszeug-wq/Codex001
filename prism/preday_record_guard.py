"""Fail-closed validation for PRISM preday forecast record envelopes.
Does not certify official racecard authenticity or predict a race.
"""
from datetime import datetime, timezone

REQUIRED = ('race_id', 'horse_id', 'horse_name', 'forecaster_id', 'source_id', 'saved_at', 'version', 'scheduled_start_at')

def parse_aware(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be string')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid timestamp') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)

def validate_preday_record(record):
    if not isinstance(record, dict):
        raise ValueError('record must be object')
    for key in REQUIRED:
        if key not in record or not isinstance(record[key], str) or not record[key].strip():
            raise ValueError(f'missing or invalid {key}')
    if record.get('source_authenticity_verified') is not True:
        raise ValueError('official source not verified')
    saved = parse_aware(record['saved_at'])
    start = parse_aware(record['scheduled_start_at'])
    if saved >= start:
        raise ValueError('saved_at must precede scheduled start')
    if record.get('record_type') != 'preday_forecast':
        raise ValueError('not a preday forecast')
    return True
