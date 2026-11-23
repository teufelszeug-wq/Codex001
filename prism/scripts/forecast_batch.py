"""Batch adapter for independently supplied PRISM forecast decisions.

Never generates missing AI forecasts or backdates saved_at.
"""
from datetime import datetime, timezone
from pathlib import Path

from forecast_snapshot_gate import validate_snapshot
from forecast_snapshot_store import save_snapshot


def persist_forecaster_batch(root, race, decisions, *, now=None):
    """Validate all supplied decisions before writing any snapshots."""
    if not isinstance(race, dict) or not isinstance(race.get("race_id"), str) or not race["race_id"]:
        raise ValueError("race_id required")
    off_at = race.get("off_at")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("at least one independently supplied decision required")
    now = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone-aware now required")
    checked = []
    keys = set()
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError("decision must be object")
        if decision.get("race_id") != race["race_id"]:
            raise ValueError("race mismatch")
        key = (decision.get("forecaster_id"), decision.get("horse_name"), decision.get("version"))
        if key in keys:
            raise ValueError("duplicate decision")
        keys.add(key)
        item = dict(decision, saved_at=now.isoformat())
        checked.append(validate_snapshot(item, off_at))
    # Best-effort rollback of this batch's files after a write failure.
    # Not a fully atomic transaction: readers may briefly see partial output.
    paths = []
    try:
        for item in checked:
            paths.append(str(save_snapshot(root, item, off_at, now=now)))
    except Exception as exc:
        cleanup_errors = []
        for path in paths:
            try:
                Path(path).unlink()
            except OSError as cleanup_exc:
                cleanup_errors.append(f"{path}: {cleanup_exc}")
        if cleanup_errors:
            raise RuntimeError(
                "batch save failed and rollback was incomplete: "
                + "; ".join(cleanup_errors)
            ) from exc
        raise
    return {
        "race_id": race["race_id"],
        "saved_count": len(paths),
        "paths": paths,
        "forecaster_count": len({item["forecaster_id"] for item in checked}),
    }
