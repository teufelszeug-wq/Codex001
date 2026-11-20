"""Batch preday persistence: validates the complete field before writing any forecast.
This does not authenticate source data or produce predictions.
"""
from pathlib import Path
from preday_record_guard import validate_preday_record
from preday_pipeline import save_preday_record

def save_preday_field(records, directory, *, as_of=None):
    if not isinstance(records, list) or not records:
        raise ValueError("nonempty forecast list required")
    root = Path(directory)
    if not root.is_dir():
        raise ValueError("destination directory missing")
    seen = set()
    paths = []
    race_ids = set()
    for record in records:
        validate_preday_record(record, as_of=as_of)
        key = (record["race_id"], record["forecaster_id"], record["horse_id"], record["version"])
        if key in seen:
            raise ValueError("duplicate forecast identity")
        seen.add(key)
        race_ids.add(record["race_id"])
        for field in ("horse_id", "forecaster_id", "version"):
            if not record[field].replace("_", "").replace("-", "").isalnum():
                raise ValueError("unsafe identity")
        name = "__".join((record["race_id"], record["forecaster_id"], record["horse_id"], record["version"]))
        if not all(c.isalnum() or c in "_-" for c in name):
            raise ValueError("unsafe race identity")
        path = root / (name + ".json")
        if path.exists():
            raise FileExistsError(path)
        paths.append(path)
    if len(race_ids) != 1:
        raise ValueError("multiple races in batch")
    written = []
    try:
        for record, path in zip(records, paths):
            save_preday_record(record, path, as_of=as_of)
            written.append(path)
    except BaseException:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return paths
