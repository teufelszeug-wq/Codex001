"""Immutable pre-day prediction records; experimental adapter, not an official-data claim."""
import json
import os
from datetime import datetime
from pathlib import Path
from .pre_day_record import validate

def persist_prediction(lock, runners, *, predictor_id, source, saved_at, version, output_dir):
    """Write one validated record per runner without overwriting an existing version.

    Caller must supply the actual saved_at; a later run cannot backdate an artifact.
    """
    if not isinstance(lock, dict) or not isinstance(runners, list):
        raise ValueError("invalid prediction payload")
    if not isinstance(lock.get("win"), dict) or not lock.get("lock_hash"):
        raise ValueError("missing prediction lock")
    # A prediction cannot be recorded as saved before its own model lock.
    # A later persistence operation must retain its real save timestamp.
    try:
        saved_dt = datetime.fromisoformat(saved_at)
        locked_dt = datetime.fromisoformat(lock["locked_at"])
        if saved_dt.tzinfo is None or locked_dt.tzinfo is None:
            raise ValueError("naive persistence timestamp")
        if saved_dt < locked_dt:
            raise ValueError("saved_at predates prediction lock")
    except (TypeError, KeyError, AttributeError) as exc:
        raise ValueError("invalid persistence timestamp") from exc
    if len(runners) != len(lock["win"]):
        raise ValueError("runner coverage mismatch")
    if not all(isinstance(x, dict) for x in runners):
        raise ValueError("invalid runner")
    ids = [x.get("horse_id") for x in runners]
    if len(set(ids)) != len(ids) or set(ids) != set(lock["win"]):
        raise ValueError("runner identity mismatch")
    records = []
    for runner in runners:
        rec = validate({
            "race_id": lock["race_id"],
            "horse_id": runner["horse_id"],
            "horse_name": runner["horse_name"],
            "predictor_id": predictor_id,
            "source": source,
            "saved_at": saved_at,
            "version": version,
            "cutoff": lock["cutoff"],
            "stage": "PRE_DAY",
            "prediction_hash": lock["lock_hash"],
            "win_probability": lock["win"][runner["horse_id"]],
        })
        probability = rec["win_probability"]
        if type(probability) not in (int, float) or not 0 <= probability <= 1:
            raise ValueError("invalid probability")
        records.append(rec)
    if abs(sum(x["win_probability"] for x in records) - 1) > 1e-6:
        raise ValueError("probabilities not normalized")
    # Avoid path injection by using a digest of the identity tuple as the filename.
    import hashlib
    key = json.dumps([lock["race_id"], predictor_id, version], ensure_ascii=False)
    name = hashlib.sha256(key.encode("utf-8")).hexdigest() + ".json"
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / name
    payload = {"schema": "prism.preday.saved/v1", "records": records}
    # Exclusive create prevents silently replacing any previously committed prediction.
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def persist_prediction_now(lock, runners, *, predictor_id, source, version, output_dir):
    """Production-facing entrypoint: capture the current UTC clock, never caller-supplied time.

    This does not authenticate source timestamps or establish third-party time attestation.
    Historical synthetic fixtures should continue using persist_prediction directly.
    """
    from datetime import timezone
    saved_at = datetime.now(timezone.utc).isoformat()
    return persist_prediction(lock, runners, predictor_id=predictor_id,
                              source=source, saved_at=saved_at,
                              version=version, output_dir=output_dir)
