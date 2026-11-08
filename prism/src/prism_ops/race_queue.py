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
    # A race with competing input revisions is ambiguous: never select the
    # first revision by incidental list order for a PRE lock.
    versions = {}
    for record in races:
        if isinstance(record, dict):
            rid, version = record.get("race_id"), record.get("input_sha256")
            if rid and version:
                versions.setdefault(rid, set()).add(version)
    conflicted = {rid for rid, hashes in versions.items() if len(hashes) > 1}
    for race in races:
        if not isinstance(race, dict):
            blocked.append({"race_id":None, "reason":"INVALID_RACE_RECORD"})
            continue
        rid = race.get("race_id")
        version = race.get("input_sha256")
        if rid in conflicted:
            blocked.append({"race_id":rid, "reason":"CONFLICTING_INPUT_VERSIONS"})
            continue
        if not rid or not version or (rid, version) in seen:
            blocked.append({"race_id":rid, "reason":"MISSING_ID_HASH_OR_DUPLICATE"})
            continue
        seen.add((rid, version))
        try:
            off = _aware(race["scheduled_off"])
        except (KeyError, ValueError, TypeError):
            blocked.append({"race_id":rid,"reason":"INVALID_OFF_TIME"})
            continue
        if off <= current or race.get("result_exposed") is True:
            blocked.append({"race_id":rid,"reason":"NO_PRE_WINDOW"})
        elif race.get("result_exposed") is not False:
            blocked.append({"race_id":rid,"reason":"RESULT_EXPOSURE_NOT_EXCLUDED"})
        elif race.get("pre_locked") is True:
            blocked.append({"race_id":rid,"reason":"ALREADY_LOCKED"})
        elif race.get("pre_locked") is not False:
            blocked.append({"race_id":rid,"reason":"PRE_LOCK_STATUS_UNVERIFIED"})
        elif race.get("official_entries_verified") is not True:
            blocked.append({"race_id":rid,"reason":"OFFICIAL_DATA_MISSING"})
        else:
            eligible.append(race)
    eligible.sort(key=lambda r: _aware(r["scheduled_off"]))
    return {"eligible":eligible,"blocked":blocked}

def snapshot_gate(forecast, receipt, now, proof_bundle=None, *, verifier_context=None):
    """A saved file and a claimed timestamp alone do not constitute verified PRE."""
    from prism_ops.forecast_completion_gate import validate_forecast
    v = validate_forecast(forecast, receipt, proof_bundle, verifier_context=verifier_context)
    errors = list(v["errors"])
    if not isinstance(receipt, dict):
        receipt = None
    if not receipt or receipt.get("forecast_sha256") != v["sha256"]:
        errors.append("PERSISTENCE_READBACK_FAILED")
    if not receipt or receipt.get("timestamp_verified") is not True:
        errors.append("EXTERNAL_TIMESTAMP_UNVERIFIED")
    if not receipt or not receipt.get("immutable_location"):
        errors.append("IMMUTABLE_LOCATION_MISSING")
    try:
        if not isinstance(forecast, dict):
            raise ValueError("INVALID_FORECAST")
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
