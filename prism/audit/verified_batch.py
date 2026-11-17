"""Publish one complete verified race prediction batch without overwriting prior versions."""
import hashlib
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from .pre_race_store import _time

def publish_verified_batch(directory, card, predictions, *, predictor_id, version, source, evidence, saved_at, now=None):
    if card.get("schema") != "prism.official_racecard/v1" or card.get("source_verified") is not True:
        raise ValueError("verified official racecard required")
    runners = card.get("active_runners")
    if not isinstance(runners, list) or not runners or not isinstance(predictions, dict):
        raise ValueError("missing runners or predictions")
    official = {r["horse_id"]: r["horse_name"] for r in runners}
    if len(official) != len(runners) or set(predictions) != set(official):
        raise ValueError("incomplete or duplicate runner identities")
    saved = _time(saved_at)
    off = _time(card["off_at"])
    actual = _time(now) if now else datetime.now(timezone.utc)
    if saved > actual or saved >= off or actual >= off:
        raise ValueError("not a valid pre-race snapshot")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("evidence required")
    for e in evidence:
        available = _time(e["available_at"])
        if available > saved:
            raise ValueError("future evidence")
        for k in ("occurred_at", "observed_at", "captured_at"):
            if k in e and _time(e[k]) > available:
                raise ValueError("backdated evidence")
    rows = []
    for runner in runners:
        horse_id = runner["horse_id"]
        prediction = predictions[horse_id]
        if not isinstance(prediction, dict) or not prediction:
            raise ValueError("missing model output")
        rows.append(dict(race_id=card["race_id"], horse_id=horse_id,
            horse_name=official[horse_id], predictor_id=predictor_id,
            source=source, saved_at=saved_at, version=version,
            off_at=card["off_at"], kind="pre_race",
            prediction=prediction, evidence=evidence))
    payload = json.dumps(dict(schema="prism.prediction_batch/v1", snapshots=rows),
        ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    key = (card["race_id"], predictor_id, version)
    name = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest() + ".batch.json"
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".pending-", dir=root)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        target = root / name
        os.link(tmp, target)
        dirfd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        return target
    finally:
        os.unlink(tmp)
