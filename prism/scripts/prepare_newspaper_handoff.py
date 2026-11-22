"""Adapter between PRISM forecast history and the M-PAPER publisher.

The existing build_paper_handoff.inspect is the authoritative input gate.
This adapter never invents a newspaper, and it refuses blocked histories.
"""
import argparse
import json
from pathlib import Path
import sys

from build_paper_handoff import inspect


def prepare(history: Path, race_id: str, output: Path) -> dict:
    handoff = inspect(history, race_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return handoff


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--race-id", required=True)
    parser.add_argument("--out", type=Path, required=True, help="handoff JSON destination")
    args = parser.parse_args()
    try:
        report = prepare(args.history, args.race_id, args.out)
    except (ValueError, FileNotFoundError, KeyError, TypeError) as exc:
        print(json.dumps({"state": "BLOCKED", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "READY_FOR_LAYOUT" else 2


if __name__ == "__main__":
    sys.exit(main())
