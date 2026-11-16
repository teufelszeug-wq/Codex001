"""Persist post-race settlement separately from immutable pre-race forecasts.

The result document is caller-supplied; this module does NOT independently
authenticate the official source URL or prove pre-off Git publication.
"""
import hashlib
import json
import os
from pathlib import Path
from settle_release import settle_release


def publish_settlement(forecast_path, official_path, output_dir):
    summary = settle_release(forecast_path, official_path)
    official_raw = Path(official_path).read_bytes()
    summary["official_input_sha256"] = hashlib.sha256(official_raw).hexdigest()
    payload = json.dumps(summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    race = summary["race_id"]
    if not isinstance(race, str) or not race or not all(c.isascii() and (c.isalnum() or c in "-_") for c in race):
        raise ValueError("unsafe race_id")
    version = summary["version"]
    directory = Path(output_dir) / race
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"settlement-v{version}-{digest}.json"
    for existing in directory.glob(f"settlement-v{version}-*.json"):
        if existing != target:
            raise ValueError("conflicting settlement version; use a new version for corrections")
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise ValueError("existing settlement altered")
        return str(target), False
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return str(target), True


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        raise SystemExit("usage: publish_settlement.py FORECAST.json OFFICIAL.json OUTPUT_DIR")
    path, created = publish_settlement(*sys.argv[1:])
    print(json.dumps({"path": path, "created": created}, ensure_ascii=False))
