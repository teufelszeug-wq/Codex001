"""Local PRE snapshot evidence, deliberately NOT external VERIFIED_PRE.

Atomic exclusive creation, canonical JSON, hash-chained append-only event files.
A host administrator can rewrite local files and clock: LOCAL_PRE is not trusted
third-party timestamp evidence and must never authorize official settlement.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def sha256(raw):
    return hashlib.sha256(raw).hexdigest()

def _write_exclusive(path, data):
    path = Path(path)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise

def _read_events(folder):
    folder = Path(folder)
    files = sorted(folder.glob("event-*.json"))
    previous = "0" * 64
    for index, path in enumerate(files, 1):
        if path.name != f"event-{index:08d}.json":
            raise ValueError("AUDIT_SEQUENCE_GAP")
        data = path.read_bytes()
        event = json.loads(data)
        if data != canonical_bytes(event):
            raise ValueError("NONCANONICAL_AUDIT_EVENT")
        if event["previous_sha256"] != previous:
            raise ValueError("AUDIT_CHAIN_BROKEN")
        previous = sha256(data)
    return previous, len(files)

def save_local_snapshot(root, forecast, *, observed_at=None):
    """Create local evidence only. Caller-supplied observed_at is for testing.

    The clock is local, not independently trusted. Race off is an aware ISO time.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("TIMEZONE_REQUIRED")
    off = datetime.fromisoformat(forecast["scheduled_off"])
    if off.tzinfo is None or off.utcoffset() is None:
        raise ValueError("TIMEZONE_REQUIRED")
    if now >= off:
        raise ValueError("NO_PRE_WINDOW")
    if forecast.get("results_exposed") is not False:
        raise ValueError("RESULT_EXPOSURE_NOT_EXCLUDED")
    raw = canonical_bytes(forecast)
    key = sha256(raw)
    objects = root / "objects"
    events = root / "events"
    objects.mkdir(exist_ok=True)
    events.mkdir(exist_ok=True)
    _write_exclusive(objects / (key + ".json"), raw)
    try:
        previous, count = _read_events(events)
        event = {"kind": "LOCAL_PRE", "forecast_sha256": key,
                 "observed_at": now.isoformat(), "race_id": forecast["race_id"],
                 "previous_sha256": previous, "sequence": count + 1}
        _write_exclusive(events / f"event-{count + 1:08d}.json",
                         canonical_bytes(event))
    except BaseException:
        # Fail closed: orphaned content-addressed object is never accepted as PRE.
        raise
    return {"status": "LOCAL_PRE", "forecast_sha256": key,
            "event_sequence": count + 1}

def audit_local_snapshots(root):
    """Re-read all local objects and chained events; never returns VERIFIED_PRE."""
    root = Path(root)
    previous, count = _read_events(root / "events")
    for index in range(1, count + 1):
        event = json.loads((root / "events" / f"event-{index:08d}.json").read_bytes())
        key = event["forecast_sha256"]
        raw = (root / "objects" / (key + ".json")).read_bytes()
        if sha256(raw) != key or canonical_bytes(json.loads(raw)) != raw:
            raise ValueError("LOCAL_OBJECT_TAMPERED")
        forecast = json.loads(raw)
        if event["race_id"] != forecast["race_id"]:
            raise ValueError("RACE_ID_MISMATCH")
        if datetime.fromisoformat(event["observed_at"]) >= datetime.fromisoformat(forecast["scheduled_off"]):
            raise ValueError("NO_PRE_WINDOW")
    return {"status": "LOCAL_AUDIT_ONLY", "event_count": count,
            "chain_tip_sha256": previous, "externally_verified": False}
