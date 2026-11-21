"""Stage raw racecard JSON with provenance; never assert source authenticity."""
import argparse
import json
import os
from pathlib import Path
from official_racecard_ingest import stage_official_racecard


def stage_file(input_path, output_path, *, source_url, retrieved_at, race_id):
    source = Path(input_path)
    output = Path(output_path)
    if source.resolve() == output.resolve():
        raise ValueError("output must not overwrite source")
    record = stage_official_racecard(
        source.read_bytes(), source_url=source_url,
        retrieved_at=retrieved_at, expected_race_id=race_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(output), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("input", "source-url", "retrieved-at", "race-id", "output"):
        parser.add_argument("--" + flag, required=True)
    args = parser.parse_args()
    record = stage_file(args.input, args.output, source_url=args.source_url,
                        retrieved_at=args.retrieved_at, race_id=args.race_id)
    print(json.dumps({"race_id": record["race_id"], "status": record["provenance_status"],
                      "sha256": record["source_sha256"]}))


if __name__ == "__main__":
    main()
