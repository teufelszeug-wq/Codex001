"""Fail-closed preday forecast writer; requires externally authenticated racecard data."""
import json
import os
from pathlib import Path
from preday_record_guard import validate_preday_record

def save_preday_record(record, destination, *, as_of=None):
    validate_preday_record(record, as_of=as_of)
    path = Path(destination)
    if path.suffix != '.json':
        raise ValueError('destination must be JSON')
    if not path.parent.is_dir():
        raise ValueError('destination directory missing')
    payload = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path
