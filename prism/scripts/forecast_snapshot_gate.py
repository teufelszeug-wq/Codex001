"""Fail-closed validation for attributable pre-race forecast snapshots."""
from copy import deepcopy
from datetime import datetime

def instant(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be ISO string")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone required")
    return dt

def validate_snapshot(snapshot, off_at):
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be object")
    for key in ("race_id", "forecaster_id", "horse_name", "source", "version"):
        if not isinstance(snapshot.get(key), str) or not snapshot[key].strip():
            raise ValueError(f"missing {key}")
    if instant(snapshot.get("saved_at")) >= instant(off_at):
        raise ValueError("not a pre-race snapshot")
    status = snapshot.get("status")
    if status not in ("pick", "pass"):
        raise ValueError("invalid status")
    if status == "pick":
        if snapshot.get("mark") not in ("◎", "○", "▲", "△", "☆"):
            raise ValueError("pick requires mark")
        ids = snapshot.get("evidence_ids")
        if not isinstance(ids, list) or not ids or any(not isinstance(e, str) or not e.strip() for e in ids):
            raise ValueError("pick requires evidence IDs")
    elif snapshot.get("mark") is not None:
        raise ValueError("pass cannot have mark")
    return deepcopy(snapshot)
