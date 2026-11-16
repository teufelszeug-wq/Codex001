"""Live-only forecast publication gate; historical imports must use a separate workflow."""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from forecast_preflight import validate
from forecast_release import release

def publish_live(source, destination, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    doc = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("document must be object")
    errors = validate(doc)
    if errors:
        raise ValueError("preflight failed: " + ",".join(errors))
    saved = datetime.fromisoformat(doc["saved_at"])
    off = datetime.fromisoformat(doc["off_at"])
    # Caller-supplied saved_at is not evidence of publication time.
    if now >= off:
        raise ValueError("live publication rejected: race already started")
    if saved > now + timedelta(minutes=2):
        raise ValueError("live publication rejected: saved_at is in the future")
    path, digest, created = release(source, destination)
    return {"path": path, "sha256": digest, "created": created,
            "published_at": now.isoformat(), "provenance": "local_clock_only",
            "historical_import": False}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output_dir")
    args = parser.parse_args()
    print(json.dumps(publish_live(args.input, args.output_dir), ensure_ascii=False))
