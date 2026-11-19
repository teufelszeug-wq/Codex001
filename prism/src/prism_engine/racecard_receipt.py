"""Create a reproducible provenance receipt for a locally captured racecard.

A digest proves byte identity, NOT that the source is official or trustworthy.
The receipt deliberately never asserts source_authenticity_verified.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def capture_racecard(path, *, source_url, captured_at=None):
    file_path = Path(path)
    raw_bytes = file_path.read_bytes()
    if not raw_bytes:
        raise ValueError("empty racecard")
    if not isinstance(source_url, str) or not source_url.startswith("https://"):
        raise ValueError("source_url must be an https URL")
    instant = datetime.now(timezone.utc) if captured_at is None else datetime.fromisoformat(captured_at)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("capture time must be timezone aware")
    document = json.loads(raw_bytes)
    if not isinstance(document, dict):
        raise ValueError("racecard JSON must be an object")
    race_id = document.get("race_id")
    runners = document.get("runners")
    if not isinstance(race_id, str) or not race_id.strip():
        raise ValueError("race_id required")
    if not isinstance(runners, list) or not runners:
        raise ValueError("nonempty runners required")
    identities = []
    for runner in runners:
        if not isinstance(runner, dict):
            raise ValueError("invalid runner")
        horse_id, name = runner.get("horse_id"), runner.get("horse_name")
        if not isinstance(horse_id, str) or not horse_id.strip():
            raise ValueError("horse_id required")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("full horse_name required")
        identities.append(horse_id)
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate horse_id")
    return {
        "schema": "prism.racecard.receipt/v1",
        "race_id": race_id,
        "runner_count": len(runners),
        "source_url": source_url,
        "captured_at": instant.isoformat(),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "source_authenticity_verified": False,
        "note": "Byte-level capture receipt only; official provenance remains unverified.",
    }


def save_receipt(receipt, directory):
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    name = receipt["sha256"] + ".receipt.json"
    path = destination / name
    with path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, sort_keys=True, indent=2)
    return path
