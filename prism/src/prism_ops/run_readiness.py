"""PRISM execution readiness audit: race-unique PRE counting, fail closed."""
from prism_ops.race_queue import next_work, snapshot_gate

def audit_run(races, now, saved_forecasts=None, official_denominator=None):
    """Only count unique verified races, never snapshot versions as distinct races.

    This is a structural audit, not independent verification of receipt authenticity.
    """
    saved_forecasts = saved_forecasts or []
    queue = next_work(races, now)
    verified_by_race = {}
    rejected = []
    for item in saved_forecasts:
        forecast = item.get("forecast") or {}
        race_id = forecast.get("race_id")
        if not race_id:
            rejected.append({"race_id":None,"verified_pre":False,"errors":["RACE_ID_MISSING"]})
            continue
        gate = snapshot_gate(forecast, item.get("receipt"), now)
        if gate["verified_pre"]:
            if race_id in verified_by_race:
                rejected.append({"race_id":race_id, **gate, "verified_pre":False,
                                 "errors":["DUPLICATE_VERIFIED_RACE_VERSION"]})
            else:
                verified_by_race[race_id] = {"race_id":race_id, **gate}
        else:
            rejected.append({"race_id":race_id, **gate})
    if type(official_denominator) is not int or official_denominator < 0:
        official_denominator = None
    if official_denominator is not None and len(verified_by_race) > official_denominator:
        raise ValueError("PRE_COUNT_EXCEEDS_DENOMINATOR")
    return {"official_race_denominator":official_denominator,
            "official_denominator_verified":official_denominator is not None,
            "eligible_races":[r["race_id"] for r in queue["eligible"]],
            "blocked":queue["blocked"],
            "verified_pre_count":len(verified_by_race),
            "verified_pre":list(verified_by_race.values()),
            "unverified_pre":rejected,
            "unsettled_count":None,
            "newspaper_complete_count":None,
            "status":"OFFICIAL_DATA_MISSING" if official_denominator is None else
                     ("PRE_LOCK_FAILED" if rejected else "PREDICTION_INCOMPLETE")}
