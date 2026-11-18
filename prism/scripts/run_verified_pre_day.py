"""Execute official evidence -> core prediction -> immutable pre-race publication.

Requires externally verified official card and source-backed horse histories.
Never manufactures predictions or treats a post-race replay as pre-race.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'prism' / 'src'))

from prism.audit.official_input_gate import validate_engine_input
from prism.audit.engine_publish import publish_engine_lock
from prism.scripts.assemble_official_engine_input import assemble_engine_input
from prism_engine import predict


def run(card, evidence, *, venue, surface, distance_m, direction,
        class_rating, barrier_count, locked_at, output_dir, predictor_id,
        version, source, source_evidence, now=None):
    # The gate's canonical number field differs from the assembler's horse_no.
    # Reconcile only when both representations agree; never silently remap IDs.
    card = dict(card)
    runners = []
    for runner in card.get("active_runners", []):
        r = dict(runner)
        if "horse_no" in r and "horse_number" in r and str(r["horse_no"]) != str(r["horse_number"]):
            raise ValueError("conflicting official horse numbers")
        if "horse_no" not in r:
            r["horse_no"] = r.get("horse_number")
        if "horse_number" not in r:
            r["horse_number"] = r.get("horse_no")
        runners.append(r)
    card["active_runners"] = runners
    validate_engine_input(card, as_of=locked_at)
    actual = datetime.now(timezone.utc) if now is None else datetime.fromisoformat(now.replace("Z", "+00:00"))
    if actual.tzinfo is None:
        raise ValueError("actual time must be timezone-aware")
    cutoff = datetime.fromisoformat(locked_at.replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        raise ValueError("prediction cutoff must be timezone-aware")
    if cutoff > actual:
        raise ValueError("prediction cutoff cannot be in the future at publication")
    off_at = datetime.fromisoformat(card["off_at"].replace("Z", "+00:00"))
    if off_at.tzinfo is None:
        raise ValueError("official off time must be timezone-aware")
    if actual >= off_at:
        raise ValueError("cannot publish pre-race after off")
    raw, names = assemble_engine_input(
        card, evidence, venue=venue, surface=surface, distance_m=distance_m,
        direction=direction, class_rating=class_rating,
        barrier_count=barrier_count, locked_at=locked_at)
    if {str(horse_id) for horse_id in names} != {str(r["horse_id"]) for r in runners}:
        raise ValueError("assembled horse IDs do not match official card")
    # Never backdate the publication timestamp to the prediction cutoff.
    # Recheck the real clock after potentially expensive inference.
    lock = predict(raw, locked_at)
    # Publication time must be measured from the real clock even when a test\n    # supplies `now` for deterministic pre-inference validation.\n    published_at = datetime.now(timezone.utc)\n    if published_at >= off_at:
        raise ValueError("prediction completed after off time")
    return publish_engine_lock(
        output_dir, card, lock, predictor_id=predictor_id, version=version,
        source=source, evidence=source_evidence, saved_at=published_at.isoformat(), now=published_at.isoformat())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON with card, evidence, race, and publication metadata")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    race = payload["race"]
    target = run(payload["card"], payload["evidence"],
        venue=race["venue"], surface=race["surface"],
        distance_m=race["distance_m"], direction=race["direction"],
        class_rating=race["class_rating"], barrier_count=race["barrier_count"],
        locked_at=payload["locked_at"], output_dir=args.out,
        predictor_id=payload["predictor_id"], version=payload["version"],
        source=payload["source"], source_evidence=payload["source_evidence"])
    print(json.dumps({"saved_file": str(target), "status": "pre_race_saved"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
