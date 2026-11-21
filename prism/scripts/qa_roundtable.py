"""Audit saved roundtables against Notion character snapshots and racecard evidence.

This is a release gate, not a generator or proof of independent model execution.
Usage: python prism/scripts/qa_roundtable.py --racecard card.json --roundtable roundtable.json --characters characters.json
Characters must be a current Notion export with entries {url,name,role,setting_status}.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

REQUIRED_TOPICS = ("全頭診断", "コース馬場", "調教・状態・取材", "本命比較・反論", "買い目")
def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def audit(card, discussion, characters):
    failures = []
    cid = card.get("race_id")
    if not cid or discussion.get("race_id") != cid:
        failures.append("RACE_ID_MISMATCH")
    runners = [r for r in card.get("runners", []) if r.get("status") not in ("SCRATCHED", "EXCLUDED")]
    names = [r.get("horse_name") for r in runners]
    if not names or any(not n for n in names):
        failures.append("INVALID_OFFICIAL_RUNNERS")
    topics = discussion.get("topics", [])
    if not isinstance(topics, list) or len(topics) < 5:
        failures.append("FEWER_THAN_FIVE_TOPICS")
        topics = []
    for topic in REQUIRED_TOPICS:
        if not any(topic in str(t.get("title", "")) for t in topics if isinstance(t, dict)):
            failures.append("MISSING_TOPIC:" + topic)
    speeches = [s for t in topics if isinstance(t, dict) for s in t.get("speeches", [])]
    character_by_url = {c["url"]: c for c in characters if c.get("url") and c.get("name")}
    if not character_by_url:
        failures.append("CHARACTER_DB_NOT_VERIFIED")
    for index, speech in enumerate(speeches):
        who = character_by_url.get(speech.get("character_url"))
        if not who or who["name"] != speech.get("name"):
            failures.append(f"UNKNOWN_CHARACTER:{index}")
            continue
        if not speech.get("character_version") or not speech.get("verified_at"):
            failures.append(f"CHARACTER_PROVENANCE_MISSING:{index}")
        if not speech.get("text", "").strip():
            failures.append(f"EMPTY_SPEECH:{index}")
        if speech.get("execution_mode") == "independent" and not speech.get("execution_id"):
            failures.append(f"INDEPENDENT_EXECUTION_UNVERIFIED:{index}")
    text = "\n".join(str(s.get("text", "")) for s in speeches)
    missing = [name for name in names if name not in text]
    if missing:
        failures.append("RUNNERS_NOT_DISCUSSSED:" + ",".join(missing))
    if not any(s.get("name", "").replace(" ", "") == "篠宮律" for s in speeches):
        failures.append("EDITOR_MISSING")
    if not any(s.get("name") == "りお" for s in speeches):
        failures.append("RIO_MISSING")
    if speeches and speeches[-1].get("name") != "りお":
        failures.append("RIO_FINAL_VIEW_MISSING")
    completed = discussion.get("completed_at")
    off = card.get("off_at")
    try:
        end = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        start = datetime.fromisoformat(off.replace("Z", "+00:00"))
        if not end.tzinfo or not start.tzinfo or end >= start:
            failures.append("NOT_VERIFIED_PRE_RACE")
    except (ValueError, TypeError, AttributeError):
        failures.append("INVALID_TIMESTAMPS")
    return {"schema": "prism.roundtable_qa/v1", "race_id": cid,
            "status": "PASS" if not failures else "FAIL",
            "runner_count": len(runners), "topics": len(topics),
            "speeches": len(speeches), "characters_verified": len(character_by_url),
            "characters_in_speeches": len(set(s.get("character_url") for s in speeches)),
            "text_chars": len(text), "missing_horses": missing,
            "failures": failures,
            "independent_execution_claims": sum(s.get("execution_mode") == "independent" for s in speeches)}

def main():
    parser = argparse.ArgumentParser()
    for name in ("racecard", "roundtable", "characters"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = audit(read(args.racecard), read(args.roundtable), read(args.characters))
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__":
    sys.exit(main())
