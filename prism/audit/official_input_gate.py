"""Fail-closed preflight for verified official racecards before prediction execution."""
from datetime import datetime, timezone

def utc(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be ISO8601 string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)

def validate_engine_input(card, *, as_of):
    """Validate identity and cutoff; source_verified must be established by caller."""
    if not isinstance(card, dict) or card.get("schema") != "prism.official_racecard/v1":
        raise ValueError("official racecard schema required")
    if card.get("source_verified") is not True:
        raise ValueError("official source must be verified externally")
    if not isinstance(card.get("source_url"), str) or not card["source_url"].startswith("https://"):
        raise ValueError("official source URL required")
    if not isinstance(card.get("race_id"), str) or not card["race_id"].strip():
        raise ValueError("race_id required")
    cutoff, off = utc(as_of), utc(card.get("off_at"))
    if cutoff >= off:
        raise ValueError("prediction cutoff must precede off time")
    runners = card.get("active_runners")
    if not isinstance(runners, list) or len(runners) < 2:
        raise ValueError("at least two runners required")
    ids, names, numbers = set(), set(), set()
    for runner in runners:
        if not isinstance(runner, dict):
            raise ValueError("runner must be object")
        horse_id, name, number = runner.get("horse_id"), runner.get("horse_name"), runner.get("horse_number")
        if not isinstance(horse_id, str) or not horse_id.strip() or not isinstance(name, str) or not name.strip():
            raise ValueError("horse identity required")
        if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
            raise ValueError("horse number must be positive integer")
        if horse_id in ids or name in names or number in numbers:
            raise ValueError("duplicate runner identity")
        ids.add(horse_id); names.add(name); numbers.add(number)
    return {"race_id": card["race_id"], "cutoff": cutoff.isoformat(), "off_at": off.isoformat(), "runner_count": len(runners), "horse_ids": sorted(ids)}
