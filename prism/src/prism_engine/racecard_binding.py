"""Bind a racecard receipt to pipeline input without claiming official authenticity."""
import hashlib
import json
from pathlib import Path


def verify_racecard_binding(racecard_path, receipt_path, payload):
    raw_bytes = Path(racecard_path).read_bytes()
    receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    card = json.loads(raw_bytes)
    if receipt.get("schema") != "prism.racecard.receipt/v1":
        raise ValueError("unsupported receipt schema")
    if receipt.get("sha256") != hashlib.sha256(raw_bytes).hexdigest():
        raise ValueError("racecard digest mismatch")
    if receipt.get("race_id") != card.get("race_id"):
        raise ValueError("receipt race_id mismatch")
    runners = card.get("runners")
    if not isinstance(runners, list) or not runners:
        raise ValueError("empty racecard runners")
    if receipt.get("runner_count") != len(runners):
        raise ValueError("receipt runner_count mismatch")
    card_pairs = [(r["horse_id"], r["horse_name"]) for r in runners]
    if len({i for i, _ in card_pairs}) != len(card_pairs):
        raise ValueError("duplicate horse_id")
    raw = payload["raw"]
    if raw["race"]["race_id"] != card["race_id"]:
        raise ValueError("pipeline race_id mismatch")
    pipeline_ids = [r["horse_id"] for r in raw["runners"]]
    if len(pipeline_ids) != len(set(pipeline_ids)):
        raise ValueError("duplicate pipeline horse_id")
    if set(pipeline_ids) != {i for i, _ in card_pairs}:
        raise ValueError("pipeline runners mismatch")
    names = payload["horse_names"]
    if names != dict(card_pairs):
        raise ValueError("pipeline horse names mismatch")
    if not receipt.get("source_url") or not receipt.get("captured_at"):
        raise ValueError("incomplete receipt")
    if raw["source"].get("source_id") != receipt["sha256"]:
        raise ValueError("pipeline source_id must equal captured racecard digest")
    return {"race_id": card["race_id"], "sha256": receipt["sha256"],
            "source_authenticity_verified": False}


def run_verified(racecard_path, receipt_path, payload, output_dir):
    """Verify binding first; existing pipeline retains pre-day cutoff and save guards."""
    binding = verify_racecard_binding(racecard_path, receipt_path, payload)
    # A matching digest proves identity, not that the source is official.
    # Never emit an operational pre-day record from an unauthenticated receipt.
    if binding["source_authenticity_verified"] is not True:
        raise ValueError("official source authenticity unverified; refuse operational save")
    from .preday_pipeline import run
    return run(payload, output_dir)
