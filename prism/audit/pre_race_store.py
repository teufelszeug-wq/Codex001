"""Append-only pre-race snapshot store; never backfill a prediction after off-time."""
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

def _time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed

def append_prediction(path, snapshot, *, now=None):
    required = ("race_id", "horse_name", "predictor_id", "source", "saved_at", "version", "off_at", "kind")
    if any(not snapshot.get(k) for k in required):
        raise ValueError("missing required snapshot field")
    if snapshot["kind"] != "pre_race":
        raise ValueError("only pre-race predictions permitted")
    saved, off = _time(snapshot["saved_at"]), _time(snapshot["off_at"])
    actual = _time(now) if now else datetime.now().astimezone()
    if saved > actual:
        raise ValueError("future-dated save")
    if actual >= off or saved >= off:
        raise ValueError("race already started")
    for evidence in snapshot.get("evidence", []):
        available = _time(evidence["available_at"])
        if available > saved:
            raise ValueError("future evidence")
        for key in ("occurred_at", "observed_at", "captured_at"):
            if key in evidence and _time(evidence[key]) > available:
                raise ValueError("backdated evidence")
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    key = (snapshot["race_id"], snapshot["horse_name"], snapshot["predictor_id"], snapshot["version"])
    filename = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest() + ".json"
    target = directory / filename
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(snapshot, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return target
