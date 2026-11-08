"""Ordinary PRE forecast assessment, separate from Golden/RFC3161 acceptance.

An ordinary PRE forecast can be used for editorial work without external proof.
It is never counted as independently verified Golden/Forward ROI.
"""
from datetime import datetime
import hashlib
import json

def assess_ordinary_forecast(forecast, *, observed_at):
    errors = []
    if not isinstance(forecast, dict):
        return {"usable": False, "status": "PREDICTION_INCOMPLETE",
                "errors": ["INVALID_FORECAST"], "eligible_for_golden_roi": False}
    try:
        def aware(s):
            t = datetime.fromisoformat(s)
            if t.utcoffset() is None:
                raise ValueError("TIMEZONE_REQUIRED")
            return t
        now = aware(observed_at)
        saved = aware(forecast["saved_at"])
        off = aware(forecast["scheduled_off"])
        source = aware(forecast["source_as_of"])
        if saved > now:
            errors.append("FUTURE_SAVED_AT")
        if source > saved:
            errors.append("SOURCE_AFTER_SAVE")
        if source >= off:
            errors.append("SOURCE_NOT_PRE_RACE")
        if saved >= off:
            errors.append("NOT_PRE_RACE")
        if now >= off:
            errors.append("PRE_WINDOW_CLOSED")
    except (KeyError, ValueError, TypeError):
        errors.append("INVALID_TIME")
    if forecast.get("results_exposed") is not False:
        errors.append("RESULT_EXPOSURE_NOT_EXCLUDED")
    if not all(isinstance(forecast.get(k), str) and forecast[k].strip()
               for k in ("race_id", "forecast_version", "input_hash")):
        errors.append("MISSING_FORECAST_IDENTITY")
    snapshot = forecast.get("input_snapshot")
    if not isinstance(snapshot, (dict, list)):
        errors.append("INPUT_SNAPSHOT_MISSING")
    else:
        raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode()
        if hashlib.sha256(raw).hexdigest() != forecast.get("input_hash"):
            errors.append("INPUT_HASH_MISMATCH")
    entries = forecast.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("INVALID_ENTRIES")
        entries = []
    names = {}
    for e in entries:
        if (not isinstance(e, dict) or type(e.get("horse_no")) is not int or
                e["horse_no"] < 1 or not isinstance(e.get("horse_name"), str) or
                not e["horse_name"].strip() or e["horse_no"] in names):
            errors.append("INVALID_ENTRIES")
            continue
        names[e["horse_no"]] = e["horse_name"]
    agents = forecast.get("agents")
    roster = forecast.get("required_agent_ids")
    if not isinstance(agents, list) or not agents:
        errors.append("INVALID_AGENTS")
        agents = []
    if (not isinstance(roster, list) or not roster or
            any(not isinstance(x, str) or not x for x in roster) or
            len(set(roster)) != len(roster)):
        errors.append("INVALID_ROSTER")
        roster = []
    ids = [a.get("agent_id") for a in agents if isinstance(a, dict)]
    if (len(ids) != len(agents) or len(ids) != len(set(ids)) or
            set(ids) != set(roster)):
        errors.append("AGENT_COVERAGE_INCOMPLETE")
    editorial = forecast.get("editorial")
    if not isinstance(editorial, dict):
        errors.append("EDITORIAL_MISSING")
        editorial = {}
    for agent in [*agents, dict(editorial, agent_id="EDITORIAL")]:
        if not isinstance(agent, dict):
            errors.append("INVALID_AGENT")
            continue
        agent_id = agent.get("agent_id", "UNKNOWN")
        picks = agent.get("picks")
        if not isinstance(picks, list) or not picks:
            errors.append(f"{agent_id}:PICKS_MISSING")
        else:
            for p in picks:
                if (not isinstance(p, dict) or
                        p.get("horse_name") != names.get(p.get("horse_no")) or
                        not p.get("mark")):
                    errors.append(f"{agent_id}:INVALID_PICK")
        tickets = agent.get("tickets")
        if not isinstance(tickets, list):
            errors.append(f"{agent_id}:INVALID_TICKETS")
            continue
        if not tickets and not agent.get("pass_reason"):
            errors.append(f"{agent_id}:NO_TICKETS_OR_PASS")
        for t in tickets:
            if (not isinstance(t, dict) or type(t.get("stake_yen")) is not int or
                    t["stake_yen"] != 100 or not t.get("bet_type") or
                    not isinstance(t.get("selection"), list) or
                    not t["selection"] or
                    any(type(n) is not int or n not in names
                        for n in t["selection"])):
                errors.append(f"{agent_id}:INVALID_TICKET")
    usable = not errors
    return {"usable": usable,
            "status": "UNVERIFIED_PRE_FORECAST" if usable else "PREDICTION_INCOMPLETE",
            "errors": sorted(set(errors)), "eligible_for_golden_roi": False,
            "eligible_for_editorial": usable, "independent_model_runs": 0}
