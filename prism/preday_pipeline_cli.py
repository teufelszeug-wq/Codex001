"""Connect reviewed racecard and forecasts to the existing append-only preday store.

This entrypoint never authenticates a source or generates a prediction.
"""
import argparse
import json
from pathlib import Path

try:
    from .racecard_forecast_bridge import build_preday_records
    from .preday_batch_store import persist_preday_batch
except ImportError:
    from racecard_forecast_bridge import build_preday_records
    from preday_batch_store import persist_preday_batch


def run(racecard_path, forecasts_path, output_dir, forecaster_id, version):
    racecard = json.loads(Path(racecard_path).read_text(encoding="utf-8"))
    forecasts = json.loads(Path(forecasts_path).read_text(encoding="utf-8"))
    if not isinstance(racecard, dict) or racecard.get("source_authenticity_verified") is not True:
        raise ValueError("upstream source authentication required")
    records = build_preday_records(
        racecard, forecasts, forecaster_id=forecaster_id, version=version
    )
    path = persist_preday_batch(records, output_dir)
    return {"path": path, "race_id": racecard["race_id"],
            "forecaster_id": forecaster_id, "runner_count": len(records),
            "version": version}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--racecard", required=True)
    parser.add_argument("--forecasts", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--forecaster-id", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    result = run(args.racecard, args.forecasts, args.output_dir,
                 args.forecaster_id, args.version)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
