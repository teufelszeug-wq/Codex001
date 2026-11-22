"""M-PAPER publication gate: completeness beyond per-forecast validation.
Does not fabricate missing predictions or treat single-model roleplay as independent execution.
"""
from datetime import datetime

REQUIRED_MARKS = ("◎", "○", "▲", "△", "☆")

def _time(s):
    d = datetime.fromisoformat(s)
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("timezone required")
    return d

def publication_gate(race, entries, predictions, characters, required_ids, discussions, qa):
    errors = []
    if not race.get("official_source_url") or not race.get("race_id"):
        errors.append("OFFICIAL_RACE_UNVERIFIED")
    try:
        start = _time(race["start_at"])
    except (KeyError, TypeError, ValueError):
        start = None
        errors.append("START_TIME_UNVERIFIED")
    horse_ids = set()
    for e in entries:
        n, f = e.get("horse_number"), e.get("frame_number")
        if type(n) is not int or n < 1 or n in horse_ids or type(f) is not int or not 1 <= f <= 8 or not e.get("horse_name"):
            errors.append("ENTRY_INVALID")
        horse_ids.add(n)
    if not entries or not race.get("entries_verified"):
        errors.append("OFFICIAL_ENTRIES_UNVERIFIED")
    accepted = {}
    for p in predictions:
        cid = p.get("character_id")
        c = characters.get(cid)
        try:
            timely = start is not None and _time(p["saved_at"]) < start
        except (KeyError, TypeError, ValueError):
            timely = False
        marks = p.get("marks")
        bets = p.get("bets")
        valid_marks = isinstance(marks, dict) and set(marks) == set(REQUIRED_MARKS) and all(type(v) is int and v in horse_ids for v in marks.values()) and len(set(marks.values())) == 5
        valid_bets = isinstance(bets, list) and bool(bets) and all(isinstance(b, dict) and type(b.get("yen")) is int and b["yen"] > 0 and b["yen"] % 100 == 0 and b.get("selection") for b in bets)
        verified = (p.get("race_id") == race.get("race_id") and p.get("status") == "FORMAL_PRE"
                    and p.get("execution_type") == "INDEPENDENT" and timely and c is not None
                    and c.get("url") and c.get("verified_at") and p.get("source_url") and p.get("version")
                    and p.get("all_horses_diagnosed") is True and valid_marks and valid_bets)
        if not verified:
            errors.append("PREDICTION_REJECTED:" + str(p.get("prediction_id")))
        elif cid in accepted:
            errors.append("DUPLICATE_CHARACTER_FORECAST:" + str(cid))
        else:
            accepted[cid] = p
    for cid in required_ids:
        if cid not in accepted:
            errors.append("MISSING_REQUIRED_FORECAST:" + str(cid))
    if len(discussions) < 5 or any(not d.get("source_url") or not d.get("character_refs_verified") for d in discussions):
        errors.append("DISCUSSION_NOT_VERIFIED")
    if not all(qa.get(k) is True for k in ("pdf_rendered", "png_rendered", "vertical_layout", "glyphs", "rules", "source_match")):
        errors.append("RENDER_QA_INCOMPLETE")
    return {"race_id": race.get("race_id"), "status": "HOLD" if errors else "READY",
            "accepted_count": len(accepted), "errors": errors}
