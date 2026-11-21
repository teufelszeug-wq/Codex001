"""Regression checks for staging unverified racecards (no official-origin claim)."""
import json
import unittest
from datetime import datetime, timezone
from official_racecard_ingest import stage_official_racecard

URL = "https://example.org/racecard.json"
RACE = "TEST_20261122_01"

def sample(**changes):
    data = {"race_id": RACE, "scheduled_start_at": "2026-11-22T10:00:00+09:00",
            "horses": [{"horse_id": "H1", "horse_name": "架空馬一"},
                       {"horse_id": "H2", "horse_name": "架空馬二"}]}
    data.update(changes)
    return json.dumps(data, ensure_ascii=False).encode("utf-8")

def stage(raw, **kw):
    return stage_official_racecard(raw, source_url=kw.get("source_url", URL),
        retrieved_at=kw.get("retrieved_at", datetime.now(timezone.utc).isoformat()),
        expected_race_id=RACE)

class RacecardStageTests(unittest.TestCase):
    def test_staging_never_certifies_authenticity(self):
        result = stage(sample())
        self.assertIs(result["source_authenticity_verified"], False)
        self.assertEqual(result["provenance_status"], "staged_unverified")
        self.assertEqual(len(result["source_sha256"]), 64)

    def test_duplicate_runner_rejected(self):
        with self.assertRaises(ValueError):
            stage(sample(horses=[{"horse_id":"H1","horse_name":"一"},
                                 {"horse_id":"H1","horse_name":"二"}]))

    def test_wrong_race_rejected(self):
        with self.assertRaises(ValueError):
            stage(sample(race_id="OTHER"))

    def test_http_source_rejected(self):
        with self.assertRaises(ValueError):
            stage(sample(), source_url="http://example.org/card")

    def test_future_retrieval_rejected(self):
        with self.assertRaises(ValueError):
            stage(sample(), retrieved_at="2099-01-01T00:00:00+00:00")

    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            stage(sample(), retrieved_at="2026-11-21T00:00:00")

    def test_missing_start_rejected(self):
        with self.assertRaises(ValueError):
            stage(sample(scheduled_start_at=None))

    def test_naive_start_rejected(self):
        with self.assertRaises(ValueError):
            stage(sample(scheduled_start_at="2026-11-22T10:00:00"))

    def test_post_start_retrieval_rejected(self):
        with self.assertRaises(ValueError):
            stage(sample(scheduled_start_at="2020-01-01T10:00:00+09:00"))

if __name__ == "__main__":
    unittest.main()
