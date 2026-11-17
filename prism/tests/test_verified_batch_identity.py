"""Regression checks for verified batch runner identity alignment."""
import tempfile
import unittest
from datetime import datetime, timezone
from prism.audit.verified_batch import publish_verified_batch

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.card = {"schema": "prism.official_racecard/v1", "source_verified": True,
                     "race_id": "TEST-001", "off_at": "2099-01-02T12:00:00+00:00",
                     "active_runners": [{"horse_id": "h1", "horse_name": "馬甲"},
                                        {"horse_id": "h2", "horse_name": "馬乙"}]}
        self.preds = {"h1": {"horse_id": "h1", "horse_name": "馬甲", "score": 0.6},
                      "h2": {"horse_id": "h2", "horse_name": "馬乙", "score": 0.4}}
    def publish(self):
        with tempfile.TemporaryDirectory() as d:
            return publish_verified_batch(d, self.card, self.preds,
                predictor_id="test", version="v1", source="test", saved_at="2099-01-01T00:00:00+00:00",
                now="2099-01-01T00:00:01+00:00",
                evidence=[{"available_at": "2098-12-31T00:00:00+00:00"}])
    def test_swapped_names_rejected(self):
        self.preds["h1"]["horse_name"] = "馬乙"
        with self.assertRaisesRegex(ValueError, "horse_name mismatch"):
            self.publish()
    def test_swapped_ids_rejected(self):
        self.preds["h1"]["horse_id"] = "h2"
        with self.assertRaisesRegex(ValueError, "horse_id mismatch"):
            self.publish()
    def test_duplicate_official_names_rejected(self):
        self.card["active_runners"][1]["horse_name"] = "馬甲"
        with self.assertRaisesRegex(ValueError, "duplicate official horse names"):
            self.publish()
    def test_blank_official_id_rejected(self):
        self.card["active_runners"][0]["horse_id"] = ""
        with self.assertRaisesRegex(ValueError, "invalid official runner identity"):
            self.publish()
if __name__ == "__main__":
    unittest.main()
