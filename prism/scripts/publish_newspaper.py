"""Run PRISM from the newspaper request, retaining originals and restart state."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prism_paper.newspaper import render_newspaper, verify_newspaper
from run_forecast_batch import prepare, run_panel
from run_race_day import restore_history

STAGES = ["LOAD_ASSETS", "CALL_REQUIRED_WORK", "SAVE_AI_ORIGINALS", "NO_FABRICATION",
          "LAYOUT_DIAGNOSIS_AND_ROUNDTABLE", "TEXT_VERTICAL_QA", "VERIFY_PNG_PDF", "SAVE_RESUME"]
ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run_command(arguments, log):
    result = subprocess.run(arguments, text=True, capture_output=True, timeout=650, check=False)
    log.append({"arguments": list(map(str, arguments)), "returncode": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "required subprocess failed")
    return result.stdout


def publish(args):
    if not re.fullmatch(r"\d{8}-(?:JRA|NAR)-[A-Z]+-\d{2}", args.race_id):
        raise ValueError("invalid race_id")
    history = args.history.resolve()
    history.mkdir(parents=True, exist_ok=True)
    if args.resume:
        edition = args.resume.resolve()
        state = read(edition / "publication-state.json")
        if state["race_id"] != args.race_id or state["history"] != str(history):
            raise ValueError("resume identity or history mismatch")
    else:
        edition = args.out.resolve() / args.race_id / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        edition.mkdir(parents=True)
        state = {"schema": "prism.newspaper_publication/v1", "race_id": args.race_id,
                 "history": str(history), "edition": str(edition), "attempts": [],
                 "checklist": {stage: False for stage in STAGES}}
    attempt = edition / f"attempt-{len(state['attempts']) + 1:02d}"
    attempt.mkdir()
    log = []
    attempt_info = {"directory": str(attempt), "started_at": datetime.now(timezone.utc).isoformat()}
    state["attempts"].append(attempt_info)
    state["checklist"] = {name: False for name in STAGES}
    for key in ("artifacts", "pages", "paper_inputs", "qa_path", "scope", "visual_review"):
        state.pop(key, None)
    stage = STAGES[0]
    try:
        assets = [ROOT / "data/operations/forecast_roster.json", ROOT / "data/operations/forecaster_contracts.json",
                  ROOT / "data/operations/character_roles_20261123.json"]
        manifest = read(args.assets_manifest) if args.assets_manifest else {"assets": []}
        for asset in manifest["assets"]:
            path = Path(asset["path"])
            if not path.is_file() or asset.get("sha256") != sha(path):
                raise ValueError(f"existing asset missing or changed: {path}")
            assets.append(path)
        state["loaded_assets"] = [{"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size} for path in assets]
        save(attempt / "loaded-assets.json", {"assets": state["loaded_assets"], "external_manifest": manifest})
        for archive in args.restore:
            restore_history(history, archive)
        state["checklist"][stage] = True
        stage = STAGES[1]
        folder = history / args.race_id
        if not (folder / "racecard.json").exists() and not (folder / "declarations-racecard.json").exists():
            if not args.official_url:
                raise FileNotFoundError("official racecard absent; provide --official-url or --restore")
            race, _ = prepare(history, args.official_url)
            if race != args.race_id:
                raise ValueError("requested official racecard is a different race")
        numbered = folder / "racecard.json"
        card_path = numbered if numbered.exists() else folder / "declarations-racecard.json"
        card = read(card_path)
        early = card.get("entry_stage") == "DECLARATIONS"
        final_path = folder / ("declarations-v1.json" if early else "v2.json")
        discussion_path = folder / ("declarations-roundtable-v1.json" if early else "roundtable-v1.json")
        if not final_path.exists() or not discussion_path.exists():
            if datetime.fromisoformat(card["off_at"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
                raise ValueError("missing pre-race originals after off; new forecasts must not be backdated")
            configured = bool(os.environ.get("OPENAI_API_KEY", "").strip() and os.environ.get("PRISM_OPENAI_MODEL", "").strip())
            model = ("openai" if configured else "local") if args.model == "auto" else args.model
            result = run_panel(history, card_path, "local" if early else model)
            save(attempt / "forecast-run.json", result)
        state["checklist"][stage] = True
        stage = STAGES[2]
        payload_path = attempt / "newspaper-inputs.json"
        run_command(["node", str(ROOT / "scripts/export_newspaper_inputs.mjs"), "--history", str(history),
                     "--race", args.race_id, "--out", str(payload_path)], log)
        payload = read(payload_path)
        save(attempt / "execution-originals.json", {"executions": payload["executions"],
             "source_paths": payload["source_paths"], "original_forecast_sha256": payload["original_forecast_sha256"]})
        state["checklist"][stage] = True
        stage = STAGES[3]
        state["independent_api_records"] = sum(row["independent_ai_verified"] for row in payload["executions"])
        state["unexecuted_or_unverified_ai"] = [row["name"] for row in payload["executions"] if not row["independent_ai_verified"]]
        state["scope"] = payload["scope"]
        state["checklist"][stage] = True
        stage = STAGES[4]
        pdf, pngs, layout = render_newspaper(payload, attempt / "paper", args.font)
        state["checklist"][stage] = True
        stage = STAGES[5]
        qa = verify_newspaper(payload, pdf, pngs, layout)
        save(attempt / "newspaper-qa.json", qa)
        if not qa["passed"]:
            raise ValueError("newspaper QA failed: " + "; ".join(qa["failures"][:5]))
        state["checklist"][stage] = True
        stage = STAGES[6]
        state["artifacts"] = qa["artifacts"]
        state["pages"] = qa["pages"]
        state["checklist"][stage] = True
        state["status"] = "PENDING_VISUAL_REVIEW"
        state["resume_stage"] = "VISUAL_REVIEW"
        state["blocking_reasons"] = ["Generated pages need visual review; automatic checks passed."]
        state["visual_review"] = None
        state["paper_inputs"] = str(payload_path)
        state["qa_path"] = str(attempt / "newspaper-qa.json")
    except Exception as error:
        state["status"] = "INCOMPLETE"
        state["resume_stage"] = stage
        state["blocking_reasons"] = [f"{type(error).__name__}: {error}"]
        attempt_info["error"] = {"stage": stage, "type": type(error).__name__, "message": str(error)}
    finally:
        state["checklist"]["SAVE_RESUME"] = True
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        attempt_info["finished_at"] = state["updated_at"]
        state["resume_command"] = [sys.executable, str(Path(__file__).resolve()), "--race-id", args.race_id,
              "--history", str(history), "--out", str(args.out.resolve()), "--resume", str(edition), "--model", args.model,
              *(["--assets-manifest", str(args.assets_manifest.resolve())] if args.assets_manifest else []),
              *(["--official-url", args.official_url] if args.official_url else []), "--font", str(args.font)]
        save(attempt / "commands.json", log)
        save(attempt / "publication-result.json", state)
        save(edition / "publication-state.json", state)
    return state


def review(args):
    edition = args.resume.resolve()
    state = read(edition / "publication-state.json")
    if state["race_id"] != args.race_id or state["status"] not in ("PENDING_VISUAL_REVIEW", "PROVISIONAL_PUBLISHED", "PUBLISHED"):
        raise ValueError("only matching, successfully rendered editions can receive visual review")
    if not all(state["checklist"].get(name) for name in STAGES):
        raise ValueError("all required newspaper stages must pass before visual signoff")
    expected = set(range(1, state["pages"] + 1))
    pages = {int(value) for value in args.reviewed_pages.split(",")}
    if pages != expected or not args.visual_review.strip() or not args.reviewer:
        raise ValueError("visual review must identify all pages, reviewer, and observations")
    for item in state["artifacts"]:
        if not Path(item["path"]).is_file() or sha(item["path"]) != item["sha256"]:
            raise ValueError("rendered artifact changed after QA")
    state["visual_review"] = {"reviewer": args.reviewer, "pages": sorted(pages), "note": args.visual_review,
                              "reviewed_at": datetime.now(timezone.utc).isoformat(), "artifact_sha256s": [row["sha256"] for row in state["artifacts"]]}
    state["status"] = "PROVISIONAL_PUBLISHED" if state["scope"] != "RECORDED_API_FORECASTS" else "PUBLISHED"
    state["resume_stage"] = None
    state["blocking_reasons"] = []
    state["production_system_complete"] = False
    save(edition / "publication-state.json", state)
    return state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--race-id", required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--official-url")
    parser.add_argument("--assets-manifest", type=Path)
    parser.add_argument("--restore", type=Path, action="append", default=[])
    parser.add_argument("--model", choices=("auto", "local", "openai"), default="auto")
    parser.add_argument("--font", type=Path, default=Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"))
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--visual-review")
    parser.add_argument("--reviewed-pages", default="")
    parser.add_argument("--reviewer")
    args = parser.parse_args()
    if args.visual_review and not args.resume:
        parser.error("--visual-review requires --resume")
    state = review(args) if args.visual_review else publish(args)
    print(json.dumps({key: state.get(key) for key in ("status", "scope", "race_id", "edition", "checklist", "pages", "independent_api_records", "blocking_reasons", "resume_stage", "artifacts")}, ensure_ascii=False, indent=2))
    return 2 if state["status"] == "INCOMPLETE" else 0


if __name__ == "__main__":
    sys.exit(main())
