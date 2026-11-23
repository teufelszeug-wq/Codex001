"""Append-only local persistence for validated pre-race forecast snapshots."""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from forecast_snapshot_gate import validate_snapshot, instant


def save_snapshot(root, snapshot, off_at, *, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires timezone")
    recorded = dict(snapshot)
    recorded["saved_at"] = now.isoformat()
    validated = validate_snapshot(recorded, off_at)
    if instant(validated["saved_at"]) >= instant(off_at):
        raise ValueError("race already started; use retrospective record")
    race_id = validated["race_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", race_id):
        raise ValueError("unsafe race_id")
    directory = Path(root) / race_id
    directory.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(validated, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    for _ in range(5):
        target = directory / (uuid4().hex + ".json")
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            break
        except FileExistsError:
            continue
    else:
        raise FileExistsError("could not allocate unique snapshot path")
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return target
