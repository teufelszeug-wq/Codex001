"""Regression checks for the odds-baseline to preday-store integration."""
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from prism.odds_preday_pipeline_cli import run


def _card():
    now = datetime.now(timezone.utc)
    # A future race tomorrow JST, while cutoff and retrieval are in the past.
    jst = timezone(timedelta(hours=9))
    race_day = now.astimezone(jst).date() + timedelta(days=2)
    start = datetime.combine(race_day, datetime.min.time(), jst).replace(hour=12)
    observed = (now - timedelta(hours=2)).isoformat()
    retrieved = (now - timedelta(hours=1)).isoformat()
    return {
        "race_id": "SYNTHETIC-ONLY", "source_id": "TEST-NOT-OFFICIAL",
        "source_authenticity_verified": True,
        "scheduled_start_at": start.isoformat(),
        "odds_observed_at": observed, "source_retrieved_at": retrieved,
        "horses": [
            {"horse_id": "H1", "horse_name": "試験一号", "win_odds": 2.0},
            {"horse_id": "H2", "horse_name": "試験二号", "win_odds": 4.0},
        ],
    }


def test_baseline_pipeline_persists_and_rejects_overwrite(tmp_path):
    card = _card()
    input_path = tmp_path / "racecard.json"
    input_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    output = tmp_path / "out"
    result = run(input_path, output, cutoff_at=cutoff, version="synthetic-v1")
    assert result["runner_count"] == 2
    assert result["baseline_only"] is True
    assert result["source_verification"] == "upstream_assertion_only"
    assert result["snapshot_sha256"] == hashlib.sha256(Path(result["path"]).read_bytes()).hexdigest()
    saved = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    assert "試験一号" in json.dumps(saved, ensure_ascii=False)
    with pytest.raises((FileExistsError, ValueError, OSError)):
        run(input_path, output, cutoff_at=cutoff, version="synthetic-v1")


def test_future_cutoff_rejected_without_write(tmp_path):
    card = _card()
    input_path = tmp_path / "racecard.json"
    input_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        run(input_path, tmp_path / "out",
            cutoff_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
            version="synthetic-v1")
    assert not list((tmp_path / "out").glob("*.json")) if (tmp_path / "out").exists() else True


def test_stale_cutoff_rejected_without_write(tmp_path):
    card = _card()
    input_path = tmp_path / "racecard.json"
    input_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    # The synthetic card was retrieved 1 hour ago; an as-of cutoff 2 hours
    # ago is invalid even before the live freshness gate is reached.
    # Move the observation and retrieval further into the past to isolate it.
    card["odds_observed_at"] = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    card["source_retrieved_at"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    input_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="stale cutoff_at"):
        run(input_path, tmp_path / "out",
            cutoff_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            version="synthetic-stale-v1")
    assert not (tmp_path / "out").exists()


def test_post_start_live_run_rejected_even_with_valid_past_cutoff(tmp_path):
    card = _card()
    now = datetime.now(timezone.utc)
    card["scheduled_start_at"] = (now - timedelta(minutes=10)).isoformat()
    card["odds_observed_at"] = (now - timedelta(minutes=50)).isoformat()
    card["source_retrieved_at"] = (now - timedelta(minutes=40)).isoformat()
    input_path = tmp_path / "racecard.json"
    input_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="race already started"):
        run(input_path, tmp_path / "out",
            cutoff_at=(now - timedelta(minutes=30)).isoformat(),
            version="synthetic-post-start-v1")
    assert not (tmp_path / "out").exists()


def test_jst_preday_calendar_rejects_same_day_cutoff_and_execution():
    from prism.odds_preday_pipeline_cli import validate_preday_calendar
    race = "2026-11-22T15:00:00+09:00"
    with pytest.raises(ValueError, match="preday cutoff"):
        validate_preday_calendar(race, "2026-11-22T00:01:00+09:00",
                                 "2026-11-21T23:00:00+09:00")
    with pytest.raises(ValueError, match="preday execution"):
        validate_preday_calendar(race, "2026-11-21T23:00:00+09:00",
                                 "2026-11-22T00:01:00+09:00")


def test_jst_preday_calendar_accepts_previous_day_and_utc_boundary():
    from prism.odds_preday_pipeline_cli import validate_preday_calendar
    validate_preday_calendar("2026-11-22T15:00:00+09:00",
                             "2026-11-21T14:00:00Z",
                             "2026-11-21T14:30:00Z")
    with pytest.raises(ValueError, match="preday execution"):
        validate_preday_calendar("2026-11-22T15:00:00+09:00",
                                 "2026-11-21T14:00:00Z",
                                 "2026-11-21T15:01:00Z")
