"""PRISM strict PRE forecast gate and paper ROI accounting (stdlib)."""
from datetime import datetime
import hashlib
import json

def timestamp(value):
    t = datetime.fromisoformat(value)
    if t.utcoffset() is None:
        raise ValueError("timezone required")
    return t

def digest(data):
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def validate_forecast(forecast):
    errors = []
    try:
        lock = timestamp(forecast["saved_at"])
        if lock >= timestamp(forecast["scheduled_off"]):
            errors.append("NOT_PRE_RACE")
    except (KeyError, ValueError, TypeError):
        errors.append("INVALID_TIME")
        lock = None
    runners = forecast.get("entries", [])
    numbers = [r.get("horse_no") for r in runners]
    if not runners or len(numbers) != len(set(numbers)) or any(not r.get("horse_name") for r in runners):
        errors.append("INVALID_ENTRIES")
    known = set(numbers)
    agents = forecast.get("agents", [])
    ids = [a.get("agent_id") for a in agents]
    if not agents or any(not i for i in ids) or len(ids) != len(set(ids)):
        errors.append("INVALID_AGENTS")
    for agent in [*agents, dict(forecast.get("editorial") or {}, agent_id="EDITORIAL")]:
        name = agent["agent_id"]
        picks = agent.get("picks", [])
        tickets = agent.get("tickets", [])
        if not picks or any(not p.get("mark") or p.get("horse_no") not in known for p in picks):
            errors.append(name + ":INVALID_PICKS")
        if not tickets and not agent.get("pass_reason"):
            errors.append(name + ":NO_TICKETS_OR_PASS")
        for ticket in tickets:
            if ticket.get("stake_yen") != 100:
                errors.append(name + ":STAKE_NOT_100")
            if not ticket.get("bet_type") or not ticket.get("selection") or any(n not in known for n in ticket.get("selection", [])):
                errors.append(name + ":INVALID_TICKET")
    for item in forecast.get("evidence", []):
        if not item.get("source") or not item.get("kind") or not item.get("available_at"):
            errors.append("EVIDENCE_MISSING_PROVENANCE")
            continue
        try:
            if lock and timestamp(item["available_at"]) > lock:
                errors.append("FUTURE_EVIDENCE")
        except (TypeError, ValueError):
            errors.append("INVALID_EVIDENCE_TIME")
    return {"complete": not errors, "errors": errors, "race_id": forecast.get("race_id"),
            "agent_count": len(agents), "sha256": digest(forecast)}

def settle_forecast(forecast, official_result):
    gate = validate_forecast(forecast)
    if not gate["complete"]:
        raise ValueError("invalid PRE forecast: " + repr(gate["errors"]))
    if official_result.get("race_id") != forecast.get("race_id") or not official_result.get("official_source"):
        raise ValueError("race/source mismatch")
    payouts = official_result.get("payouts_per_100", {})
    report = {}
    for agent in [*forecast["agents"], dict(forecast["editorial"], agent_id="EDITORIAL")]:
        tickets = agent.get("tickets", [])
        stake = sum(t["stake_yen"] for t in tickets)
        returned = sum(payouts.get(t["bet_type"] + ":" + "-".join(map(str, t["selection"])), 0) for t in tickets)
        report[agent["agent_id"]] = {"stake_yen": stake, "payout_yen": returned,
            "net_yen": returned - stake, "roi_pct": round(100 * returned / stake, 4) if stake else None}
    return {"race_id": forecast["race_id"], "forecast_sha256": gate["sha256"],
            "official_source": official_result["official_source"], "by_agent": report}
