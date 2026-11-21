"""Generate a reproducible odds-implied baseline, not an independent AI forecast.

Input is a normalized racecard with per-runner decimal win odds and an
odds_observed_at timestamp. This module never authenticates its source.
The caller must verify authenticity and freshness before formal use.
"""
from datetime import datetime, timezone
from math import fsum, isfinite


def _aware(value, label):
    if not isinstance(value, str):
        raise ValueError(label + " required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid " + label) from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(label + " must include timezone")
    return dt.astimezone(timezone.utc)


def odds_baseline(racecard, *, cutoff_at):
    """Return complete bridge-compatible forecasts using only cutoff-eligible odds."""
    if not isinstance(racecard, dict) or racecard.get("source_authenticity_verified") is not True:
        raise ValueError("verified racecard required")
    cutoff = _aware(cutoff_at, "cutoff_at")
    start = _aware(racecard.get("scheduled_start_at"), "scheduled_start_at")
    observed = _aware(racecard.get("odds_observed_at"), "odds_observed_at")
    retrieved = _aware(racecard.get("source_retrieved_at"), "source_retrieved_at")
    if not observed <= retrieved <= cutoff < start:
        raise ValueError("odds timing violates pre-race cutoff")
    horses = racecard.get("horses")
    if not isinstance(horses, list) or not horses:
        raise ValueError("nonempty horses required")
    ids, weights = set(), []
    for horse in horses:
        if not isinstance(horse, dict) or not isinstance(horse.get("horse_id"), str) or not horse["horse_id"].strip():
            raise ValueError("invalid horse identity")
        if horse["horse_id"] in ids:
            raise ValueError("duplicate horse")
        ids.add(horse["horse_id"])
        odds = horse.get("win_odds")
        if isinstance(odds, bool) or not isinstance(odds, (int, float)) or not isfinite(odds) or odds <= 1:
            raise ValueError("complete decimal win_odds > 1 required")
        weights.append(1.0 / odds)
    total = fsum(weights)
    return [{"horse_id": h["horse_id"],
             "prediction": {"win_probability": w / total,
                            "model_id": "odds_implied_baseline_v1",
                            "odds_observed_at": racecard["odds_observed_at"]}}
            for h, w in zip(horses, weights)]
