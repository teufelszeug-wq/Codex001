"""Immutable local PRISM forecast release; does not prove Git timing."""
import hashlib
import contextlib
import time
import os
if os.name == "nt":
    import msvcrt
else:
    import fcntl
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from forecast_preflight import validate

@contextlib.contextmanager
def exclusive_lock(handle):
    """Cross-process advisory lock for POSIX and Windows, held until release."""
    if os.name == "nt":
        handle.seek(0)
        if handle.read(1) == b"":
            handle.seek(0)
            handle.write(bytes([0]))
            handle.flush()
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def release(source, destination, live_off_at=None):
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
    with open(lock_path, "a+b") as lock, exclusive_lock(lock):
        # Check actual wall clock *inside* the publication lock. A prior
        # check in the caller can become stale while waiting for this lock.
        if live_off_at is not None:
            if live_off_at.tzinfo is None or live_off_at.utcoffset() is None:
                raise ValueError("live_off_at must be timezone-aware")
            if datetime.now(timezone.utc) >= live_off_at:
                raise ValueError("live publication rejected: deadline passed during release")
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

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: forecast_release.py INPUT.json OUTPUT_DIR")
    path, sha, created = release(sys.argv[1], sys.argv[2])
    print(json.dumps({"path": path, "sha256": sha, "created": created}, ensure_ascii=False))
