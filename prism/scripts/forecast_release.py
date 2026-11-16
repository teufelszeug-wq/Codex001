"""Immutable local PRISM forecast release; does not prove Git timing."""
import hashlib
import fcntl
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
    # Serialize version checks and creation across concurrent publisher processes.
    # The lock lives outside the release glob and is never treated as a release.
    lock_path = target_dir / ".release.lock"
    with open(lock_path, "a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if any(p != target for p in target_dir.glob(f"v{doc['version']}-*.json")):
                raise ValueError("version already published with different payload")
            try:
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
            except FileExistsError:
                if target.read_bytes() != payload:
                    raise ValueError("hash collision or altered existing release")
                return str(target), digest, False
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(payload)
                    f.flush()
                    os.fsync(f.fileno())
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            return str(target), digest, True
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: forecast_release.py INPUT.json OUTPUT_DIR")
    path, sha, created = release(sys.argv[1], sys.argv[2])
    print(json.dumps({"path": path, "sha256": sha, "created": created}, ensure_ascii=False))
