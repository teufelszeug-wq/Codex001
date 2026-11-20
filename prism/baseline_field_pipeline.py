"""Run the explicitly uncalibrated pre-race baseline and persist a verified field.

This is a wiring layer, not an official racecard fetcher or independent AI.
Never treat a caller-provided authenticity flag as proof of official origin.
"""
from datetime import datetime, timezone
from prerace_baseline import forecast_field
from verified_field_pipeline import persist_verified_field


def persist_baseline_field(racecard, feature_rows, directory, *, cutoff_at,
                           version="baseline_v1", as_of=None):
    """Return saved paths. No backdated production writes are permitted."""
    if as_of is not None:
        raise ValueError("as_of override prohibited in production entrypoint")
    observed = datetime.now(timezone.utc)
    cutoff = datetime.fromisoformat(cutoff_at.replace("Z", "+00:00"))
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff timezone required")
    if cutoff.astimezone(timezone.utc) > observed:
        raise ValueError("future feature cutoff prohibited")
    forecasts = forecast_field(racecard, feature_rows, cutoff_at=cutoff_at)
    return persist_verified_field(
        racecard, forecasts, directory,
        forecaster_id="uncalibrated_prerace_baseline_v1", version=version)
