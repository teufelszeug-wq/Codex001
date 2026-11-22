"""PRISM newspaper-first controller.

Connect the existing official racecard/forecast batch to a configured newspaper
publisher. Never count a forecast-only run as a published newspaper.
The publisher is deliberately an explicit command: no fake newspaper fallback.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "scripts" / "run_forecast_batch.py"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def check_publication(manifest: dict, out: Path, expected_races: set[str]) -> dict:
    """Publisher must return a JSON manifest with real PNG/PDF files."""
    if not isinstance(manifest, dict):
        raise ValueError("publisher manifest must be an object")
    if manifest.get("race_id") not in expected_races:
        raise ValueError("publisher race_id not in forecast batch")
    pngs = manifest.get("png_files")
    pdf = manifest.get("pdf_file")
    if not isinstance(pngs, list) or not pngs or not isinstance(pdf, str):
        raise ValueError("publisher must report png_files and pdf_file")
    root = out.resolve()

    def verify(raw: str, signature: bytes) -> str:
        if not isinstance(raw, str) or not raw:
            raise ValueError("empty artifact path")
        p = Path(raw)
        p = (root / p).resolve() if not p.is_absolute() else p.resolve()
        if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size < 16:
            raise ValueError(f"missing/invalid artifact under output directory: {raw}")
        if not p.read_bytes()[:len(signature)] == signature:
            raise ValueError(f"incorrect file signature: {raw}")
        return str(p)

    return {
        "race_id": manifest["race_id"],
        "png_files": [verify(p, b"\\x89PNG\\r\\n\\x1a\\n") for p in pngs],
        "pdf_file": verify(pdf, b"%PDF-"),
        "edition": manifest.get("edition", "UNVERIFIED"),
        "qa_status": manifest.get("qa_status", "UNVERIFIED"),
    }


def run(urls: list[str], out: Path, publisher: list[str], model: str = "local") -> dict:
    out.mkdir(parents=True, exist_ok=True)
    status_path = out / "newspaper-controller-status.json"
    status = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "state": "STARTED", "requested_urls": urls, "publications": [], "errors": [],
    }
    write_json(status_path, status)
    try:
        if not urls:
            raise ValueError("at least one official racecard URL is required")
        command = [sys.executable, str(BATCH), "--out", str(out), "--model", model]
        for url in urls:
            command.extend(["--url", url])
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
        if result.returncode:
            raise RuntimeError("forecast batch failed: " + result.stderr[-2000:])
        batch = json.loads(result.stdout)
        status["forecast_report"] = batch
        if batch.get("errors"):
            raise RuntimeError("forecast batch returned errors")
        races = batch.get("races") or []
        if not races:
            raise RuntimeError("no verified forecast races")
        status["state"] = "FORECAST_READY"
        write_json(status_path, status)
        if not publisher:
            status["state"] = "AWAITING_PUBLISHER"
            status["errors"].append("newspaper publisher command not configured; PNG/PDF not issued")
            write_json(status_path, status)
            return status
        for race in races:
            race_id = race["race_id"]
            result = subprocess.run(
                [*publisher, "--race-id", race_id, "--out", str(out)],
                capture_output=True, text=True, timeout=900,
            )
            if result.returncode:
                status["errors"].append({"race_id": race_id, "error": result.stderr[-2000:]})
                continue
            try:
                publication = check_publication(json.loads(result.stdout), out, {race_id})
                status["publications"].append(publication)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                status["errors"].append({"race_id": race_id, "error": str(error)})
            write_json(status_path, status)
        status["state"] = "PUBLISHED" if len(status["publications"]) == len(races) and not status["errors"] else "PARTIAL"
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        status["errors"].append(str(error))
        status["state"] = "FAILED"
    status["finished_at"] = datetime.now(timezone.utc).isoformat()
    write_json(status_path, status)
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", choices=("local", "openai"), default="local")
    parser.add_argument("--publisher", default="", help="Existing publisher executable and fixed arguments")
    args = parser.parse_args()
    report = run(args.url, args.out, shlex.split(args.publisher), args.model)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["state"] == "PUBLISHED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
