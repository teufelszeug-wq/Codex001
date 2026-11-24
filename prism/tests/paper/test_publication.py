"""Behavioral publication checks; all racing inputs below are explicitly synthetic."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
pytest.importorskip("fitz")
pytest.importorskip("PIL")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("prism_publication", ROOT / "scripts/publish_newspaper.py")
publication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publication)


def options(tmp_path):
    now = datetime.now(timezone.utc)
    day = (now + timedelta(days=2)).date().isoformat()
    race = day.replace("-", "") + "-JRA-TOKYO-11"
    return SimpleNamespace(race_id=race, history=tmp_path / "history", out=tmp_path / "output",
        assets_manifest=None, restore=[], resume=None, official_url=None, model="local",
        font=Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
        visual_review=None, reviewed_pages="", reviewer=None)


def card(args, expired=False):
    now = datetime.now(timezone.utc)
    day = args.race_id[:8]
    race_date = f"{day[:4]}-{day[4:6]}-{day[6:]}"
    value = {"schema": "prism.official_racecard/v1", "authority": "JRA", "race_id": args.race_id,
      "race_name": "架空新聞接続テスト", "race_date": race_date, "venue": "東京", "race_no": 11,
      "off_at": (now - timedelta(hours=1)).isoformat() if expired else race_date + "T15:30:00+09:00",
      "captured_at": (now - timedelta(hours=2)).isoformat(),
      "official_url": "https://www.jra.go.jp/JRADB/accessD.html?CNAME=synthetic",
      "source_verified": True, "source_verification": "JRA_RACECARD_IDENTITY_MATCH", "source_sha256": "f" * 64,
      "course": {"surface": "TURF", "distance_m": 1800, "direction": "LEFT"},
      "runners": [{"horse_no": n, "horse_name": f"架空馬{n}", "frame_no": n,
        "horse_id": str(2024000000 + n), "status": "DECLARED", "jockey_name": "架空騎手",
        "official_rating": 110 - n, "win_odds": 5 * n, "carried_weight": 56,
        "pedigree": {"sire": "架空父"}, "history": [{"date": (now - timedelta(days=30)).date().isoformat(),
          "venue": "東京", "surface": "TURF", "distance_m": 1800, "finish": n,
          "field_size": 10, "rating": 110 - n, "last_3f": 34 + n, "first_call": n,
          "jockey_name": "架空騎手"}]} for n in (1, 2, 3)]}
    folder = args.history / args.race_id
    folder.mkdir(parents=True)
    (folder / "racecard.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return folder


def test_startup_asset_failure_preserves_exact_restart_location(tmp_path):
    args = options(tmp_path)
    args.assets_manifest = tmp_path / "assets.json"
    args.assets_manifest.write_text(json.dumps({"assets": [{"path": str(tmp_path / "missing"), "sha256": "0" * 64}]}))
    state = publication.publish(args)
    assert state["status"] == "INCOMPLETE"
    assert state["resume_stage"] == "LOAD_ASSETS"
    assert state["checklist"]["SAVE_RESUME"] is True
    assert state["checklist"]["CALL_REQUIRED_WORK"] is False
    assert Path(state["edition"], "publication-state.json").is_file()
    assert "--resume" in state["resume_command"]


def test_never_backdates_a_missing_forecast_after_the_race(tmp_path):
    args = options(tmp_path)
    folder = card(args, expired=True)
    state = publication.publish(args)
    assert state["status"] == "INCOMPLETE"
    assert state["resume_stage"] == "CALL_REQUIRED_WORK"
    assert "backdated" in state["blocking_reasons"][0]
    assert not (folder / "v1.json").exists()


def test_render_failure_resume_retains_originals_and_verifies_real_files(tmp_path, monkeypatch):
    args = options(tmp_path)
    if not args.font.exists():
        pytest.skip("Japanese CJK font needed for PDF rendering")
    folder = card(args)
    renderer = publication.render_newspaper
    def broken(*arguments):
        raise OSError("synthetic interrupted renderer")
    monkeypatch.setattr(publication, "render_newspaper", broken)
    first = publication.publish(args)
    assert first["resume_stage"] == "LAYOUT_DIAGNOSIS_AND_ROUNDTABLE"
    original = (folder / "v2.json").read_bytes()
    initial = (folder / "v1.json").read_bytes()
    assert len(json.loads(original)["records"]) == 19
    assert all(row["independent_execution"] is False for row in json.loads(original)["records"])
    monkeypatch.setattr(publication, "render_newspaper", renderer)
    args.resume = Path(first["edition"])
    second = publication.publish(args)
    assert second["status"] == "PENDING_VISUAL_REVIEW", second.get("blocking_reasons")
    assert all(second["checklist"].values())
    assert second["independent_api_records"] == 0
    assert len(second["unexecuted_or_unverified_ai"]) == 19
    assert (folder / "v1.json").read_bytes() == initial
    assert (folder / "v2.json").read_bytes() == original
    assert len(second["artifacts"]) == second["pages"] + 1
    assert all(Path(item["path"]).stat().st_size > 100 for item in second["artifacts"])
    args.visual_review = "合成検証用の申告。実紙面の人間による目視を認定しない。"
    args.reviewer = "synthetic-test"
    args.reviewed_pages = "1"
    with pytest.raises(ValueError, match="all pages"):
        publication.review(args)
    args.reviewed_pages = ",".join(str(n) for n in range(1, second["pages"] + 1))
    png = Path(second["artifacts"][-1]["path"])
    png.write_bytes(png.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="changed after QA"):
        publication.review(args)
