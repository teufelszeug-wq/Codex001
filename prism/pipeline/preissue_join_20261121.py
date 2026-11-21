"""Strict timezone-aware preissue validation for PRISM M-PAPER.
Only independently persisted, verified forecasts are eligible; empty input always HOLD.
"""
from datetime import datetime

MARKS = ("◎", "○", "▲", "△", "☆")

def _instant(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone offset required")
    return dt

def build_preissue(race, entries, predictions, characters):
    errors = []
    try:
        start = _instant(race["start_at"])
    except (KeyError, TypeError, ValueError):
        start = None
        errors.append("INVALID_RACE_START")
    horses = {}
    for entry in entries:
        number = entry.get("horse_number")
        frame = entry.get("frame_number")
        if (type(number) is not int or number < 1 or number in horses
                or type(frame) is not int or not 1 <= frame <= 8
                or not entry.get("horse_name")):
            errors.append("OFFICIAL_ENTRIES_INCOMPLETE")
        horses[number] = entry
    if not entries:
        errors.append("OFFICIAL_ENTRIES_INCOMPLETE")
    accepted = []
    for p in predictions:
        reasons = []
        if p.get("race_id") != race.get("race_id"):
            reasons.append("RACE_ID_MISMATCH")
        if p.get("status") != "FORMAL_PRE" or p.get("execution_type") == "EDITORIAL_SINGLE_MODEL":
            reasons.append("NOT_FORMAL_PRE")
        try:
            saved = _instant(p["saved_at"])
            if start is None or saved >= start:
                reasons.append("LATE_OR_UNKNOWN_START")
        except (KeyError, ValueError, TypeError):
            reasons.append("INVALID_SAVED_AT")
        character = characters.get(p.get("character_id"))
        if not character or not all(character.get(k) for k in ("url", "role", "verified_at")):
            reasons.append("CHARACTER_UNVERIFIED")
        if not p.get("source_url") or not p.get("version"):
            reasons.append("SOURCE_UNVERIFIED")
        marks = p.get("marks")
        if not isinstance(marks, dict) or set(marks) != set(MARKS):
            reasons.append("MARKS_INCOMPLETE")
        elif (any(type(n) is not int or n not in horses for n in marks.values())
              or len(set(marks.values())) != len(MARKS)):
            reasons.append("HORSE_MISMATCH_OR_DUPLICATE")
        bets = p.get("bets")
        if (not isinstance(bets, list) or not bets
                or any(not isinstance(b, dict) or type(b.get("yen")) is not int
                       or b["yen"] <= 0 or b["yen"] % 100 != 0 for b in bets)):
            reasons.append("INVALID_100YEN_BETS")
        if reasons:
            errors.append({"prediction_id": p.get("prediction_id"), "reasons": reasons})
        else:
            accepted.append(p)
    if not accepted:
        errors.append("NO_VERIFIED_PREISSUE_FORECAST")
    return {"race_id": race.get("race_id"),
            "status": "HOLD" if errors else "PREISSUE_READY",
            "accepted": accepted, "errors": errors}
