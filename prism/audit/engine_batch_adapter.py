"""Adapt experimental engine prediction locks to verified archival rows."""
from math import isfinite

def adapt_engine_lock(card, lock):
    if card.get("schema") != "prism.official_racecard/v1" or card.get("source_verified") is not True:
        raise ValueError("verified official racecard required")
    if lock.get("schema") != "prism.engine.prediction/v1":
        raise ValueError("engine lock required")
    if lock.get("race_id") != card.get("race_id") or lock.get("cutoff") != card.get("off_at"):
        raise ValueError("race identity or off time mismatch")
    runners = card.get("active_runners")
    if not isinstance(runners, list) or not runners:
        raise ValueError("active runners required")
    if any(not isinstance(r, dict) or not isinstance(r.get("horse_name"), str) or not r["horse_name"].strip() for r in runners):
        raise ValueError("invalid official runner identity")
    ids = [r.get("horse_id") for r in runners]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("duplicate or invalid horse ids")
    for field in ("win", "scores"):
        values = lock.get(field)
        if not isinstance(values, dict) or set(values) != set(ids):
            raise ValueError("incomplete engine output: " + field)
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) for v in values.values()):
            raise ValueError("invalid engine numeric output: " + field)
    if any(v < 0 or v > 1 for v in lock["win"].values()) or abs(sum(lock["win"].values()) - 1) > 1e-6:
        raise ValueError("invalid win distribution")
    if not lock.get("lock_hash") or not lock.get("input_hash") or not lock.get("model_version"):
        raise ValueError("missing engine provenance")
    return {r["horse_id"]: {
        "horse_id": r["horse_id"], "horse_name": r["horse_name"],
        "win_probability": lock["win"][r["horse_id"]],
        "ability_score": lock["scores"][r["horse_id"]],
        "engine_lock_hash": lock["lock_hash"], "engine_input_hash": lock["input_hash"],
        "model_version": lock["model_version"],
        "performance_validated": lock.get("performance_validated") is True
    } for r in runners}
