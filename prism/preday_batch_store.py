"""Append-only preday forecast batch persistence; never overwrites an edition.

Only records already validated by build_preday_records may be persisted.
This function does not authenticate a racecard or generate forecasts.
"""
import json
import os
import re
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
    first = records[0]
    for record in records:
        if any(record[k] != first[k] for k in ("race_id", "forecaster_id", "version", "saved_at")):
            raise ValueError("mixed forecast batch")
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
