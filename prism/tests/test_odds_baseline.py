"""Synthetic regression tests for cutoff-safe odds baseline."""
import unittest
from prism.odds_baseline import odds_baseline

class OddsBaselineTest(unittest.TestCase):
    def setUp(self):
        self.card = {
            "source_authenticity_verified": True,
            "scheduled_start_at": "2026-11-24T12:00:00+09:00",
            "odds_observed_at": "2026-11-23T10:00:00+09:00",
            "source_retrieved_at": "2026-11-23T10:01:00+09:00",
            "horses": [{"horse_id": "a", "win_odds": 2.0},
                       {"horse_id": "b", "win_odds": 4.0}],
        }

    def forecast(self):
        return odds_baseline(self.card, cutoff_at="2026-11-23T11:00:00+09:00")

    def test_normal(self):
        result = self.forecast()
        self.assertAlmostEqual(sum(x["prediction"]["win_probability"] for x in result), 1)
        self.assertEqual([x["horse_id"] for x in result], ["a", "b"])

    def test_leak(self):
        self.card["odds_observed_at"] = "2026-11-23T12:00:00+09:00"
        with self.assertRaises(ValueError):
            self.forecast()

    def test_missing_odds(self):
        del self.card["horses"][0]["win_odds"]
        with self.assertRaises(ValueError):
            self.forecast()

    def test_duplicate(self):
        self.card["horses"][1]["horse_id"] = "a"
        with self.assertRaises(ValueError):
            self.forecast()

    def test_unverified(self):
        self.card["source_authenticity_verified"] = False
        with self.assertRaises(ValueError):
            self.forecast()
