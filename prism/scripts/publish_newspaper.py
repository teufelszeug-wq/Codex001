"""M-PAPER publisher CLI using the existing vertical operational renderer.

Input is an explicitly assembled, source-backed operational bundle.
Never invents forecast records from a racecard or a handoff manifest.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prism_ops.paper import render_operational_paper


def publish(bundle_path: Path, race_id: str, out: Path, version: str = "pre-v1") -> dict:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    if bundle.get("race", {}).get("race_id") != race_id:
        raise ValueError("bundle race_id mismatch")
    if not bundle.get("race", {}).get("runners"):
        raise ValueError("source-backed race runners required")
    if not bundle.get("final"):
        raise ValueError("source-backed final forecasts required")
    if len(bundle.get("discussions", [])) < 5:
        raise ValueError("five saved roundtable topics required")
    manifest = render_operational_paper(bundle, out / race_id / "newspaper" / version, version=version)
    return {
        "race_id": race_id,
        "pdf_file": manifest["pdf"]["path"],
        "png_files": [row["path"] for row in manifest["images"]],
        "edition": version,
        "qa_status": manifest["qa"]["status"],
        "manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--race-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--version", default="pre-v1")
    args = parser.parse_args()
    try:
        print(json.dumps(publish(args.bundle, args.race_id, args.out, args.version), ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, ImportError) as exc:
        print(json.dumps({"state": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
