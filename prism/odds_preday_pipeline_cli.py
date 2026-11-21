"""Run an odds-implied *baseline* into the existing preday append-only store.

This is not an independent specialist AI forecast. The upstream producer must
authenticate the racecard and odds; a boolean alone is not proof of authenticity.
"""
import argparse
import json
from pathlib import Path

try:
    from .odds_baseline import odds_baseline
    from .racecard_forecast_bridge import build_preday_records
    from .preday_batch_store import persist_preday_batch
except ImportError:
    from odds_baseline import odds_baseline
    from racecard_forecast_bridge import build_preday_records
    from preday_batch_store import persist_preday_batch


BASELINE_ID = "odds_implied_baseline_v1"


def run(racecard_path, output_dir, *, cutoff_at, version):
    racecard = json.loads(Path(racecard_path).read_text(encoding="utf-8"))
    if not isinstance(racecard, dict):
        raise ValueError("racecard must be an object")
    # The cutoff is explicit and cannot be inferred from a later run time.
    forecasts = odds_baseline(racecard, cutoff_at=cutoff_at)
    records = build_preday_records(
        racecard, forecasts, forecaster_id=BASELINE_ID, version=version
    )
    # Do not silently re-label post-cutoff execution as an earlier snapshot.
    from datetime import datetime, timezone
    cutoff = datetime.fromisoformat(cutoff_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff_at must include timezone")
    if now < cutoff.astimezone(timezone.utc):
        raise ValueError("future cutoff_at")
    path = persist_preday_batch(records, output_dir)
    return {"path": str(path), "race_id": racecard["race_id"],
            "forecaster_id": BASELINE_ID, "runner_count": len(records),
            "version": version, "baseline_only": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--racecard", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cutoff-at", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.racecard, args.output_dir,
                         cutoff_at=args.cutoff_at, version=args.version),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
