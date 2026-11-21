"""Normalize externally retrieved official racecards without claiming source authentication.

The caller must independently verify the source and provide the raw bytes.
This adapter records a reproducible SHA-256 and retrieval time; it never sets
source_authenticity_verified=True.
"""
import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlparse


def stage_official_racecard(raw_bytes, *, source_url, retrieved_at, expected_race_id):
    if not isinstance(raw_bytes, bytes) or not raw_bytes:
        raise ValueError("nonempty raw source bytes required")
    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise ValueError("HTTPS source URL required")
    try:
        timestamp = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("invalid retrieval timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("retrieval timestamp must have timezone")
    if timestamp.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ValueError("future retrieval timestamp")
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("source must be UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("race_id") != expected_race_id:
        raise ValueError("race identity mismatch")
    scheduled = payload.get("scheduled_start_at")
    if not isinstance(scheduled, str):
        raise ValueError("scheduled start timestamp required")
    try:
        start = datetime.fromisoformat(scheduled.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid scheduled start timestamp") from exc
    if start.tzinfo is None or start.utcoffset() is None:
        raise ValueError("scheduled start timezone required")
    if timestamp.astimezone(timezone.utc) >= start.astimezone(timezone.utc):
        raise ValueError("racecard retrieved at or after scheduled start")
    horses = payload.get("horses")
    if not isinstance(horses, list) or not horses:
        raise ValueError("nonempty runner list required")
    seen = set()
    for horse in horses:
        if not isinstance(horse, dict):
            raise ValueError("invalid runner")
        hid, name = horse.get("horse_id"), horse.get("horse_name")
        if not isinstance(hid, str) or not hid.strip() or not isinstance(name, str) or not name.strip() or hid in seen:
            raise ValueError("invalid or duplicate runner identity")
        seen.add(hid)
    return {
        "race_id": expected_race_id,
        "source_id": source_url,
        "source_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "source_retrieved_at": timestamp.astimezone(timezone.utc).isoformat(),
        "source_authenticity_verified": False,
        "scheduled_start_at": payload.get("scheduled_start_at"),
        "horses": horses,
        "provenance_status": "staged_unverified",
    }
