"""Regression checks: timestamp candidates are not verified without history."""
import importlib.util
import json
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "audit_real_races.py"
spec = importlib.util.spec_from_file_location("prism_real_race_audit", MODULE)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def test_candidate_without_external_attestation(tmp_path):
    forecast = tmp_path / "forecast.json"
    forecast.write_text(json.dumps({
        "race_id": "R1", "version": 1,
        "saved_at": "2026-11-14T18:00:00+09:00",
        "off_at": "2026-11-15T15:00:00+09:00",
        "source_refs": ["official-entry"], "records": [{"forecaster_id": "F1"}],
    }), encoding="utf-8")
    report = audit_module.audit({"targets": [
        {"race_id": "R1", "off_at": "2026-11-15T15:00:00+09:00"}
    ]}, [forecast])
    assert report["pre_off_candidate_count"] == 1
    assert report["verified_pre_off_count"] == 0
    assert report["races"][0]["reason"] == "PRE_OFF_CANDIDATE_AWAITING_GIT_OR_STORAGE_HISTORY"
    assert report["pre_off_candidates"][0]["version"] == 1


def test_post_off_not_candidate(tmp_path):
    forecast = tmp_path / "late.json"
    forecast.write_text(json.dumps({
        "race_id": "R1", "version": 1,
        "saved_at": "2026-11-15T15:01:00+09:00",
        "off_at": "2026-11-15T15:00:00+09:00",
        "source_refs": ["official-entry"], "records": [{"forecaster_id": "F1"}],
    }), encoding="utf-8")
    report = audit_module.audit({"targets": [
        {"race_id": "R1", "off_at": "2026-11-15T15:00:00+09:00"}
    ]}, [forecast])
    assert report["pre_off_candidate_count"] == 0
    assert report["rejected_count"] == 1
