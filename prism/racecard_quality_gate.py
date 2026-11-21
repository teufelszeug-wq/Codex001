"""Quality gate for staged racecards. Never authenticates a source."""
from datetime import datetime, timezone

def validate_staged_card(card, *, prediction_at=None, require_verified=True):
    if not isinstance(card, dict):
        raise ValueError("staged racecard must be an object")
    required = ("race_id", "source_id", "source_sha256", "source_retrieved_at", "scheduled_start_at", "horses", "source_authenticity_verified")
    if any(k not in card for k in required):
        raise ValueError("missing racecard provenance fields")
    if not isinstance(card["race_id"], str) or not card["race_id"].strip():
        raise ValueError("invalid race_id")
    if require_verified and card["source_authenticity_verified"] is not True:
        raise ValueError("unverified source cannot enter production forecast")
    h = card["source_sha256"]
    if not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise ValueError("invalid source hash")
    def parse(s):
        if not isinstance(s, str):
            raise ValueError("timestamp must be a string")
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid timestamp") from exc
        if d.tzinfo is None or d.utcoffset() is None:
            raise ValueError("timezone required")
        return d.astimezone(timezone.utc)
    retrieved, start = parse(card["source_retrieved_at"]), parse(card["scheduled_start_at"])
    if retrieved >= start:
        raise ValueError("post-start racecard")
    if prediction_at is not None:
        prediction = parse(prediction_at)
        if prediction >= start or retrieved > prediction:
            raise ValueError("temporal leakage: invalid prediction cutoff")
    horses = card["horses"]
    if not isinstance(horses, list) or not horses:
        raise ValueError("empty field")
    ids, numbers = set(), set()
    for horse in horses:
        if not isinstance(horse, dict):
            raise ValueError("invalid horse")
        hid, name = horse.get("horse_id"), horse.get("horse_name")
        if not isinstance(hid, str) or not hid.strip() or not isinstance(name, str) or not name.strip() or hid in ids:
            raise ValueError("invalid or duplicate horse identity")
        ids.add(hid)
        num = horse.get("horse_number")
        if num is not None:
            if type(num) is not int or num <= 0 or num in numbers:
                raise ValueError("invalid or duplicate horse number")
            numbers.add(num)
    if numbers and len(numbers) != len(horses):
        raise ValueError("partially populated horse numbers")
    return {"race_id": card["race_id"], "runner_count": len(horses), "forecast_eligible": card["source_authenticity_verified"] is True, "source_sha256": h}
