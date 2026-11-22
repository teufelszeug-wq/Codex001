"""Convert actual saved PRISM forecast + roundtable records to M-PAPER bundle.

No invented forecast, commentary, or racecard fields. This is an adapter,
not evidence that an external model was executed.
"""
import argparse
import json
from pathlib import Path
import re
import sys


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def assemble(history: Path, race_id: str) -> dict:
    if not re.fullmatch(r"\d{8}-(?:JRA|NAR)-[A-Z]+-\d{2}", race_id):
        raise ValueError("invalid race_id")
    directory = history / race_id
    cards = [directory / n for n in ("racecard.json", "declarations-racecard.json")]
    card_path = next((p for p in cards if p.is_file()), None)
    if card_path is None:
        raise FileNotFoundError("official racecard missing")
    card = read(card_path)
    versions = sorted((int(p.stem[1:]), p) for p in directory.glob("v*.json") if re.fullmatch(r"v\d+", p.stem))
    if not versions:
        raise FileNotFoundError("final forecast history missing")
    final = read(versions[-1][1])
    discussion_path = directory / "roundtable-v1.json"
    if not discussion_path.is_file():
        raise FileNotFoundError("saved five-topic roundtable missing")
    discussion = read(discussion_path)
    if any(doc.get("race_id") != race_id for doc in (card, final, discussion)):
        raise ValueError("race identity mismatch")
    if len(discussion.get("topics", [])) < 5:
        raise ValueError("five roundtable topics required")
    if not final.get("records"):
        raise ValueError("no final forecast records")
    if final.get("metadata", {}).get("phase") != "FINAL":
        raise ValueError("not a final forecast")
    if not final.get("saved_at") or not card.get("off_at"):
        raise ValueError("missing timestamps")
    from datetime import datetime
    saved = datetime.fromisoformat(final["saved_at"].replace("Z", "+00:00"))
    off = datetime.fromisoformat(card["off_at"].replace("Z", "+00:00"))
    if saved.tzinfo is None or off.tzinfo is None or saved >= off:
        raise ValueError("not a verified pre-race forecast")
    if not discussion.get("recorded_at"):
        raise ValueError("roundtable timestamp missing")
    discussed = datetime.fromisoformat(discussion["recorded_at"].replace("Z", "+00:00"))
    if discussed.tzinfo is None or discussed >= saved:
        raise ValueError("roundtable must precede final forecast")
    active = [r for r in card.get("runners", []) if r.get("status") not in ("SCRATCHED", "EXCLUDED")]
    if not active or any(not r.get("horse_name") or not isinstance(r.get("horse_no"), int) for r in active):
        raise ValueError("numbered official runner list required")
    by_no = {r["horse_no"]: r for r in active}
    if len(by_no) != len(active):
        raise ValueError("duplicate horse numbers")
    runners = [
        {"horse_id": str(r["horse_no"]), "horse_no": r["horse_no"], "frame_no": r.get("frame_no"),
         "name": r["horse_name"], "jockey_name": r.get("jockey_name"),
         "carried_weight": r.get("carried_weight"), "status": r.get("status")}
        for r in active
    ]
    def record_to_paper(record):
        diagnoses = record.get("diagnoses", [])
        if {d.get("horse_no") for d in diagnoses} != set(by_no):
            raise ValueError("incomplete all-runner diagnosis")
        return {
            "saved_at": final["saved_at"], "mode": record.get("execution", {}).get("provider", "UNVERIFIED"),
            "summary": record.get("summary", ""),
            "diagnoses": [{"horse_id": str(d["horse_no"]), "reason": d["reason"],
                           "win_probability": d.get("win_probability")} for d in diagnoses],
            "picks": [{"horse_id": str(p["horse_no"]), "mark": p.get("mark", "印未記録"),
                       "reason": p.get("reason", "")} for p in record.get("picks", [])
                      if p.get("horse_no") in by_no],
            "tickets": record.get("tickets", []), "skip_reason": record.get("skip_reason"),
        }
    forecasts = {r["forecaster_id"]: record_to_paper(r) for r in final["records"]}
    people = discussion.get("character_registry", {}).get("participants", [])
    characters = {p["speaker_id"]: {"name": p["name"], "role": "editor" if p["speaker_id"] == discussion.get("facilitator_id") else "specialist"} for p in people}
    for r in final["records"]:
        characters.setdefault(r["forecaster_id"], {"name": r.get("display_name", r["forecaster_id"]), "role": "specialist"})
    topics = [{
        "topic_id": t.get("id"), "title": t.get("title"),
        "moderator_id": discussion.get("facilitator_id"),
        "started_at": discussion.get("opened_at"), "completed_at": discussion["recorded_at"],
        "turns": [{"agent_id": turn.get("speaker_id"), "text": turn.get("text", ""),
                   "evidence_refs": turn.get("evidence_refs", [])} for turn in t.get("turns", [])]
    } for t in discussion["topics"]]
    backend = final.get("metadata", {}).get("model_backend")
    mode = "single_model_simulation" if backend == "local_rules" else "UNVERIFIED"
    return {
        "mode": mode,
        "race": {"race_id": race_id, "race_name": card.get("race_name", final.get("race_name", race_id)),
                 "authority": race_id.split("-")[1], "off_at": card["off_at"], "runners": runners},
        "characters": characters, "preliminary": {}, "final": forecasts,
        "discussions": topics, "source_refs": final.get("source_refs", []),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--race-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = assemble(args.history, args.race_id)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"state": "BUNDLE_READY", "race_id": args.race_id, "path": str(args.out)}, ensure_ascii=False))
        return 0
    except (ValueError, FileNotFoundError, KeyError, TypeError) as error:
        print(json.dumps({"state": "BLOCKED", "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
