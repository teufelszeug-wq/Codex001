"""Append-only preday forecast batch persistence; never overwrites an edition.

Only records already validated by build_preday_records may be persisted.
This function does not authenticate a racecard or generate forecasts.
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta
from math import fsum, isclose, isfinite
from pathlib import Path

_REQUIRED = ("race_id", "horse_id", "horse_name", "forecaster_id", "source_id", "saved_at", "version")

def persist_preday_batch(records, output_dir):
    if not isinstance(records, list) or not records:
        raise ValueError("nonempty forecast batch required")
    for record in records:
        if not isinstance(record, dict) or any(not isinstance(record.get(k), str) or not record[k].strip() for k in _REQUIRED):
            raise ValueError("missing normalized forecast identity")
        if record.get("record_type") != "preday_forecast" or record.get("source_authenticity_verified") is not True:
            raise ValueError("only authenticated preday forecasts may be persisted")
    def aware(value, field):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise ValueError("invalid " + field) from exc
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError(field + " requires timezone")
        return dt.astimezone(timezone.utc)

    first = records[0]
    saved = aware(first["saved_at"], "saved_at")
    if saved > datetime.now(timezone.utc):
        raise ValueError("future saved_at")
    start = aware(first.get("scheduled_start_at"), "scheduled_start_at")
    jst = timezone(timedelta(hours=9))
    if saved >= start or saved.astimezone(jst).date() >= start.astimezone(jst).date():
        raise ValueError("not a preday forecast in JST")

    for record in records:
        if any(record[k] != first[k] for k in ("race_id", "forecaster_id", "version", "saved_at", "source_id", "scheduled_start_at")):
            raise ValueError("mixed forecast batch")
    # Provenance time is mandatory for a formal live preday edition.
    # Missing timestamps previously passed whenever all records omitted them.
    for record in records:
        retrieved = aware(record.get("source_retrieved_at"), "source_retrieved_at")
        if retrieved > saved:
            raise ValueError("source retrieved after saved_at")
        # Presence must agree as well as value: a missing timestamp in the
        # first record previously allowed later records to supply one.
        if record.get("source_retrieved_at") != first.get("source_retrieved_at"):
            raise ValueError("mixed source retrieval times")
    probabilities = [r.get("prediction", {}).get("win_probability")
                     if isinstance(r.get("prediction"), dict) else None for r in records]
    # A formal preday forecast must contain a complete, normalized probability vector.
    # Previously an all-missing vector bypassed validation and was persisted.
    if any(isinstance(p, bool) or not isinstance(p, (int, float))
           or not isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError("missing or invalid win_probability")
    if not isclose(fsum(probabilities), 1.0, rel_tol=0, abs_tol=1e-8):
        raise ValueError("win_probability sum must equal 1")
    ids = [r["horse_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate horse_id")
    def safe(value):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", value) or value in (".", ".."):
            raise ValueError("unsafe path identifier")
        return value
    filename = "__".join(safe(first[k]) for k in ("race_id", "forecaster_id", "version")) + ".json"
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    payload = (json.dumps(records, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")
    # O_EXCL prevents concurrent writers and preserves previous editions.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return str(target)
