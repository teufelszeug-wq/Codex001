"""Build an evidence-based M-PAPER handoff manifest from a saved PRISM race.

This does not claim that a newspaper or independent AI session was produced.
Run: python prism/scripts/build_paper_handoff.py --history forecasts --race-id ID
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys

RACE_ID = re.compile(r"\d{8}-(?:JRA|NAR)-[A-Z]+-\d{2}")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inspect(history, race_id):
    if not RACE_ID.fullmatch(race_id):
        raise ValueError("invalid race_id")
    folder = history / race_id
    if not folder.is_dir():
        raise FileNotFoundError(f"race history missing: {folder}")
    cards = [folder / name for name in ("racecard.json", "declarations-racecard.json") if (folder / name).exists()]
    if not cards:
        raise FileNotFoundError("official racecard missing")
    card = load(cards[0])
    if card.get("race_id") != race_id:
        raise ValueError("racecard race_id mismatch")
    runners = [r for r in card.get("runners", []) if r.get("status") not in ("SCRATCHED", "EXCLUDED")]
    if not runners or any(not r.get("horse_name") for r in runners):
        raise ValueError("runner names missing")
    versions = sorted((int(p.stem[1:]), p) for p in folder.glob("v*.json") if re.fullmatch(r"v\d+", p.stem))
    final = load(versions[-1][1]) if versions else None
    errors = []
    if not final:
        errors.append("NO_FINAL_FORECAST")
    elif final.get("race_id") != race_id:
        errors.append("FINAL_RACE_ID_MISMATCH")
    else:
        saved = datetime.fromisoformat(final["saved_at"].replace("Z", "+00:00"))
        off = datetime.fromisoformat(card["off_at"].replace("Z", "+00:00"))
        if saved.tzinfo is None or off.tzinfo is None or saved >= off:
            errors.append("NO_VERIFIED_PRE_RACE_SAVE")
    # A roundtable is evidence only when the actual saved discussion is present.
    discussion = folder / "roundtable-v1.json"
    discussion_data = load(discussion) if discussion.exists() else None
    if not discussion_data:
        errors.append("NO_SAVED_ROUNDTABLE")
    # Never infer actual independent execution from a simulated transcript.
    if final and final.get("metadata", {}).get("model_backend") == "local_rules":
        errors.append("LOCAL_MODEL_NOT_INDEPENDENT_AI")
    return {
        "schema": "prism.paper_handoff/v1",
        "race_id": race_id,
        "official_racecard": str(cards[0]),
        "runner_count": len(runners),
        "runners": [{"horse_no": r.get("horse_no"), "horse_name": r["horse_name"]} for r in runners],
        "forecast_path": str(versions[-1][1]) if versions else None,
        "roundtable_path": str(discussion) if discussion_data else None,
        "status": "READY_FOR_LAYOUT" if not errors else "BLOCKED",
        "blocking_reasons": errors,
        "paper_pdf_path": None,
        "paper_generated": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--race-id", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = inspect(args.history, args.race_id)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "READY_FOR_LAYOUT" else 2


if __name__ == "__main__":
    sys.exit(main())
