"""PRISM execution readiness audit. Does not certify external sources."""
from prism_ops.race_queue import next_work, snapshot_gate

def audit_run(races, now, saved_forecasts=None):
    """Do not count locally hashed drafts as certified PRE."""
    saved_forecasts = saved_forecasts or []
    queue = next_work(races, now)
    verified = []
    rejected = []
    for item in saved_forecasts:
        gate = snapshot_gate(item["forecast"], item.get("receipt"), now)
        target = verified if gate["verified_pre"] else rejected
        target.append({"race_id":item["forecast"].get("race_id"), **gate})
    return {"official_race_denominator":None,
            "official_denominator_verified":False,
            "eligible_races":[r["race_id"] for r in queue["eligible"]],
            "blocked":queue["blocked"],
            "verified_pre_count":len(verified),
            "verified_pre":verified,
            "unverified_pre":rejected,
            "unsettled_count":None,
            "newspaper_complete_count":None,
            "status":"OFFICIAL_DATA_MISSING" if not races else
                     ("PRE_LOCK_FAILED" if rejected else "PREDICTION_INCOMPLETE")}
