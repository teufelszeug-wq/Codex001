"""Regression: retrieval timestamp consistency is independent of record order."""
from datetime import datetime, timedelta, timezone
import unittest
import tempfile
from pathlib import Path
from prism.preday_batch_store import persist_preday_batch


class RetrievalPresenceTests(unittest.TestCase):
    def test_mixed_source_retrieval_presence_rejected_both_orders(self):
        now = datetime.now(timezone.utc)
        # Race tomorrow in Japan, with the saved timestamp on the previous JST day.
        jst = timezone(timedelta(hours=9))
        tomorrow = now.astimezone(jst).date() + timedelta(days=2)
        start = datetime.combine(tomorrow, datetime.min.time(), jst).replace(hour=12).isoformat()
        base = dict(race_id="JRA_TEST_1", forecaster_id="baseline", version="v1",
                    source_id="test", saved_at=now.isoformat(),
                    scheduled_start_at=start, record_type="preday_forecast",
                    source_authenticity_verified=True)
        first = dict(base, horse_id="h1", horse_name="馬一",
                     prediction={"win_probability": 0.6})
        second = dict(base, horse_id="h2", horse_name="馬二",
                      source_retrieved_at=(now - timedelta(minutes=5)).isoformat(),
                      prediction={"win_probability": 0.4})
        for order in ([first, second], [second, first]):
            with pytest.raises(ValueError, match="mixed source retrieval times"):
                persist_preday_batch(order, tmp_path)
            assert not list(tmp_path.glob("*.json"))
