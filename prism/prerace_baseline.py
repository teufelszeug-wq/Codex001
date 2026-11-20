"""Deterministic pre-race baseline, NOT a calibrated PRISM model.
Only explicitly timestamped pre-race features are accepted. No results are read.
"""
from datetime import datetime, timezone
from math import exp, isfinite

def _instant(value):
    if not isinstance(value, str):
        raise ValueError('timestamp must be ISO-8601 text')
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('invalid timestamp') from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)

def forecast_field(racecard, feature_rows, *, cutoff_at):
    """Return one forecast per runner for bridge; no persistence or authentication."""
    if not isinstance(racecard, dict) or racecard.get('source_authenticity_verified') is not True:
        raise ValueError('verified racecard required')
    cutoff = _instant(cutoff_at)
    start = _instant(racecard['scheduled_start_at'])
    if cutoff >= start:
        raise ValueError('cutoff must precede race start')
    horses = racecard.get('horses')
    if not isinstance(horses, list) or not horses:
        raise ValueError('nonempty field required')
    if not isinstance(feature_rows, list):
        raise ValueError('feature rows required')
    ids = [h['horse_id'] for h in horses]
    if any(not isinstance(hid, str) or not hid for hid in ids) or len(set(ids)) != len(ids):
        raise ValueError('invalid or duplicate runner')
    features = {}
    for row in feature_rows:
        if not isinstance(row, dict) or row.get('horse_id') not in ids or row['horse_id'] in features:
            raise ValueError('unknown or duplicate feature runner')
        if _instant(row['observed_at']) > cutoff:
            raise ValueError('post-cutoff feature leakage')
        score = row.get('pre_race_score')
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not isfinite(score):
            raise ValueError('finite numeric pre_race_score required')
        features[row['horse_id']] = float(score)
    if set(features) != set(ids):
        raise ValueError('feature coverage incomplete')
    maximum = max(features.values())
    weights = {hid: exp(features[hid] - maximum) for hid in ids}
    total = sum(weights.values())
    if not isfinite(total) or total <= 0:
        raise ValueError('invalid score normalization')
    return [{'horse_id': hid, 'prediction': {'win_probability': weights[hid] / total,
            'model_id': 'uncalibrated_prerace_baseline_v1', 'feature_cutoff_at': cutoff_at}}
            for hid in ids]
