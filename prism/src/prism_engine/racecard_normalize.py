"""Normalize a captured JSON racecard without authenticating its source."""
import hashlib
import json
from pathlib import Path

def normalize_candidate(source_path, metadata_path):
    raw = Path(source_path).read_bytes()
    meta = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    if meta.get("schema") != "prism.source.capture/v1":
        raise ValueError("unsupported capture metadata")
    if hashlib.sha256(raw).hexdigest() != meta.get("sha256"):
        raise ValueError("capture digest mismatch")
    if meta.get("source_authenticity_verified") is not False:
        raise ValueError("capture authenticity flag must remain unverified")
    try:
        card = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("structured JSON racecard required; HTML unsupported") from exc
    if not isinstance(card, dict) or not isinstance(card.get("race_id"), str) or not card["race_id"].strip():
        raise ValueError("race_id required")
    runners = card.get("runners")
    if not isinstance(runners, list) or not runners:
        raise ValueError("runners required")
    ids, numbers, normalized = set(), set(), []
    for item in runners:
        if not isinstance(item, dict):
            raise ValueError("runner must be an object")
        horse_id, name, number = item.get("horse_id"), item.get("horse_name"), item.get("horse_number")
        if not isinstance(horse_id, str) or not horse_id.strip() or not isinstance(name, str) or not name.strip():
            raise ValueError("horse_id and full horse_name required")
        if type(number) is not int or number < 1 or number > 99:
            raise ValueError("valid horse_number required")
        if horse_id in ids or number in numbers:
            raise ValueError("duplicate horse_id or horse_number")
        frame = item.get("frame_no")
        if frame is not None and (type(frame) is not int or not 1 <= frame <= 8):
            raise ValueError("frame_no must be an integer from 1 to 8")
        ids.add(horse_id)
        numbers.add(number)
        runner = {"horse_id": horse_id, "horse_name": name, "horse_number": number}
        if frame is not None:
            runner["frame_no"] = frame
        normalized.append(runner)
    return {"schema": "prism.racecard.normalized/v1", "race_id": card["race_id"],
            "runners": sorted(normalized, key=lambda x: x["horse_number"]),
            "source_id": meta["sha256"], "source_url": meta.get("final_url"),
            "source_authenticity_verified": False}
