"""Regression: failed writes must not leave an apparently valid snapshot."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from forecast_snapshot_store import save_snapshot


def test_failed_fsync_removes_partial_snapshot(tmp_path):
    now = datetime.now(timezone.utc)
    snapshot = {
        "race_id": "TEST_20261124_11",
        "forecaster_id": "honshi",
        "horse_name": "テスト馬",
        "source": "test-fixture",
        "version": "v1",
        "status": "pick",
        "mark": "◎",
        "evidence_ids": ["fixture-1"],
    }
    off_at = (now + timedelta(hours=2)).isoformat()
    with patch("forecast_snapshot_store.os.fsync", side_effect=OSError("simulated disk failure")):
        with pytest.raises(OSError, match="simulated disk failure"):
            save_snapshot(tmp_path, snapshot, off_at, now=now)
    assert list(tmp_path.rglob("*.json")) == []
