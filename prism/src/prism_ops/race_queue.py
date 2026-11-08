"""Race queue selection and fail-closed PRE snapshot eligibility.

Does not claim official source verification or trusted timestamps.
"""
from datetime import datetime

def _aware(s):
    d = datetime.fromisoformat(s)
    if d.utcoffset() is None:
        raise ValueError("TIMEZONE_REQUIRED")
    return d

def next_work(races, now):
    """Return eligible unprocessed races in off-time order, without recycling completed input."""
    current = _aware(now)
    eligible, blocked = [], []
    seen = set()
    for race in races:
        rid = race.get("race_id")
        version = race.get("input_sha256")
        if not rid or not version or (rid, version) in seen:
            blocked.append({"race_id":rid, "reason":"MISSING_ID_HASH_OR_DUPLICATE"})
            continue
        seen.add((rid, version))
        try:
            off = _aware(race["scheduled_off"])
        except (KeyError, ValueError, TypeError):
            blocked.append({"race_id":rid,"reason":"INVALID_OFF_TIME"})
            continue
        if off <= current or race.get("result_exposed"):
            blocked.append({"race_id":rid,"reason":"NO_PRE_WINDOW"})
        elif race.get("pre_locked"):
            blocked.append({"race_id":rid,"reason":"ALREADY_LOCKED"})
        elif race.get("official_entries_verified") is not True:
            blocked.append({"race_id":rid,"reason":"OFFICIAL_DATA_MISSING"})
        else:
            eligible.append(race)
    eligible.sort(key=lambda r: _aware(r["scheduled_off"]))
    return {"eligible":eligible,"blocked":blocked}

def snapshot_gate(forecast, receipt, now, proof_bundle=None):
    """A saved file and a claimed timestamp alone do not constitute verified PRE."""
    from prism_ops.forecast_completion_gate import validate_forecast
    v = validate_forecast(forecast, receipt, proof_bundle)
    errors = list(v["errors"])
    if not receipt or receipt.get("readback_sha256") != v["sha256"]:
        errors.append("PERSISTENCE_READBACK_FAILED")
    if not receipt or receipt.get("external_timestamp_verified") is not True:
        errors.append("EXTERNAL_TIMESTAMP_UNVERIFIED")
    if not receipt or not receipt.get("immutable_location"):
        errors.append("IMMUTABLE_LOCATION_MISSING")
    try:
        if _aware(forecast["saved_at"]) > _aware(now):
            errors.append("FUTURE_SAVED_AT")
        if receipt and receipt.get("trusted_saved_at"):
            trusted = _aware(receipt["trusted_saved_at"])
            if trusted > _aware(now):
                errors.append("FUTURE_TRUSTED_TIMESTAMP")
            if trusted >= _aware(forecast["scheduled_off"]):
                errors.append("TRUSTED_TIMESTAMP_AFTER_OFF")
        else:
            errors.append("TRUSTED_TIMESTAMP_MISSING")
        # Historical audits must not invalidate an authentic pre-off receipt merely
        # because the audit runs after the race. Trusted saved time is checked above.
    except (KeyError, TypeError, ValueError):
        errors.append("INVALID_OFF_TIME")
    return {"verified_pre":not errors, "errors":errors, "sha256":v["sha256"]}
