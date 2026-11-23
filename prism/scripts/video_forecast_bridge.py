"""Fail-closed bridge from verified video observations into PRISM forecast inputs.

This module never watches a video or upgrades page-only evidence to observation.
It does not mutate source records. Post-race observations remain review-only.
"""
from copy import deepcopy
from datetime import datetime
from video_evidence_gate import validate

def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def attach_video_evidence(forecast_input, evidence, *, saved_at, off_at, phase="pre_race"):
    if not isinstance(forecast_input, dict) or not isinstance(evidence, list):
        raise ValueError("input must be an object and evidence a list")
    race_id = forecast_input.get("race_id")
    runners = forecast_input.get("runners")
    if not race_id or not isinstance(runners, list):
        raise ValueError("race_id and runner list required")
    if any(not isinstance(r, dict) for r in runners):
        raise ValueError("runner records must be objects")
    names = [r.get("horse_name") for r in runners]
    if not names or any(not isinstance(n, str) or not n.strip() for n in names) or len(names) != len(set(names)):
        raise ValueError("unique named runners required")
    # Validate the forecast snapshot even when no video evidence is supplied.
    from video_evidence_gate import instant
    if phase == "pre_race":
        snapshot, off = instant(saved_at), instant(off_at)
        if snapshot is None or off is None or snapshot >= off:
            raise ValueError("pre-race forecast times invalid")
    elif phase != "review":
        raise ValueError("invalid phase")
    out = deepcopy(forecast_input)
    accepted, withheld, seen = [], [], set()
    for entry in evidence:
        if not isinstance(entry, dict):
            raise ValueError("evidence record must be object")
        eid = entry.get("evidence_id")
        if not isinstance(eid, str) or not eid.strip() or eid in seen:
            raise ValueError("duplicate or blank evidence_id")
        seen.add(eid)
        if entry.get("race_id") != race_id or entry.get("horse_name") not in names:
            raise ValueError("evidence race/horse mismatch")
        # Do not let future or review evidence silently contaminate pre-race forecasts.
        try:
            validate(entry, forecast_saved_at=saved_at, off_at=off_at, phase=phase)
        except ValueError as error:
            if phase == "pre_race" and ("future video evidence" in str(error)):
                withheld.append({"evidence_id": eid, "reason": "post_snapshot_evidence"})
                continue
            raise
        if entry["status"] not in ("partial_playback", "full_playback"):
            withheld.append({"evidence_id": eid, "reason": "no_verified_playback"})
            continue
        accepted.append(deepcopy(entry))
    out["video_evidence"] = accepted
    out["video_evidence_withheld"] = withheld
    out["video_evidence_phase"] = phase
    return out
