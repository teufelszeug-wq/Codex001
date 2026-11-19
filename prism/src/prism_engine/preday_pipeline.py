"""CLI bridge: validated raw race input -> engine -> immutable pre-day records.

This does NOT fetch or authenticate official racecards. Never label a synthetic
fixture or unverified source as an official forecast.
Usage: python -m prism_engine.preday_pipeline INPUT.json OUTPUT_DIRECTORY
Input JSON: {"raw": engine_raw, "horse_names": {horse_id: full_name},
             "predictor_id": "main", "version": "v1"}
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .engine import predict
from .preday_persistence import persist_prediction_now


def run(payload, output_dir, *, now=None):
    if not isinstance(payload, dict):
        raise ValueError("invalid pipeline input")
    raw = payload["raw"]
    if raw.get("mode") == "SYNTHETIC":
        raise ValueError("synthetic inputs are not eligible for operational pre-day records")
    names = payload["horse_names"]
    if not isinstance(names, dict):
        raise ValueError("horse_names must be an id-to-name mapping")
    runners = raw["runners"]
    ids = [r["horse_id"] for r in runners]
    if len(ids) != len(set(ids)) or set(names) != set(ids):
        raise ValueError("horse name coverage or identity mismatch")
    if any(not isinstance(names[i], str) or not names[i].strip() for i in ids):
        raise ValueError("missing full horse name")
    source = raw["source"]
    if not source.get("source_id") or source["source_id"] == "SYNTHETIC-TEST-ONLY":
        raise ValueError("missing non-synthetic source provenance")
    instant = now if now is not None else datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("naive execution clock")
    cutoff = datetime.fromisoformat(raw["race"]["cutoff"])
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("race cutoff must include a timezone offset")
    local_now = instant.astimezone(cutoff.tzinfo)
    if local_now.date() >= cutoff.date():
        raise ValueError("pre-day deadline passed; do not backdate")
    lock = predict(raw, instant.isoformat())
    mapped = [{"horse_id": i, "horse_name": names[i]} for i in ids]
    # No official/authenticity claim: source ID is preserved verbatim.
    return persist_prediction_now(
        lock, mapped, predictor_id=payload["predictor_id"],
        source=source["source_id"], version=payload["version"],
        output_dir=output_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json")
    parser.add_argument("output_directory")
    args = parser.parse_args()
    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    print(run(payload, args.output_directory))


if __name__ == "__main__":
    main()
