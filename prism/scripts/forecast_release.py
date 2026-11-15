"""Immutable local PRISM forecast release; does not prove Git timing."""
import hashlib
import json
import os
import sys
from pathlib import Path
from forecast_preflight import validate

def release(source, destination):
    doc = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("document must be object")
    errors = validate(doc)
    if errors:
        raise ValueError("preflight failed: " + ",".join(errors))
    race = doc["race_id"].strip()
    if not all(c.isalnum() or c in "-_" for c in race):
        raise ValueError("invalid:race_id_path")
    payload = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    target_dir = Path(destination) / race
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"v{doc['version']}-{digest}.json"
    if any(p != target for p in target_dir.glob(f"v{doc['version']}-*.json")):
        raise ValueError("version already published with different payload")
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError:
        if target.read_bytes() != payload:
            raise ValueError("hash collision or altered existing release")
        return str(target), digest, False
    with os.fdopen(fd, "wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    return str(target), digest, True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: forecast_release.py INPUT.json OUTPUT_DIR")
    path, sha, created = release(sys.argv[1], sys.argv[2])
    print(json.dumps({"path": path, "sha256": sha, "created": created}, ensure_ascii=False))
