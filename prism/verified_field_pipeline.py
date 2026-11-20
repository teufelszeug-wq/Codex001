"""Connect an already verified racecard and complete forecasts to immutable preday files.

This module neither fetches official data nor runs prediction models. The caller
must supply those independently; no simulation is recorded as a real forecast.
"""
from datetime import datetime, timezone
from racecard_forecast_bridge import build_preday_records
from preday_field_writer import save_preday_field


def persist_verified_field(racecard, forecasts, directory, *, forecaster_id,
                           version, as_of=None):
    """Build and persist all runners; return saved paths or fail closed.

    The timestamp is captured at the write boundary, never accepted from a
    forecast payload. Caller-supplied as_of is only for deterministic tests.
    """
    if as_of is None:
        observed = datetime.now(timezone.utc)
    elif isinstance(as_of, datetime) and as_of.tzinfo is not None and as_of.utcoffset() is not None:
        observed = as_of
    else:
        raise ValueError("as_of must be an aware datetime")
    stamp = observed.astimezone(timezone.utc).isoformat()
    records = build_preday_records(
        racecard, forecasts, forecaster_id=forecaster_id,
        version=version, saved_at=stamp
    )
    return save_preday_field(records, directory, as_of=observed)
