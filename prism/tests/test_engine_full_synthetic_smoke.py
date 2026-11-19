"""Full engine smoke test using explicitly synthetic inputs; not a real-race result."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prism_engine.contracts import digest
from prism_engine.engine import predict, post_market
from prism_engine.market import settle

LOCK = "2026-11-19T00:00:00+09:00"
CUTOFF = "2026-11-20T15:00:00+09:00"

def fixture():
    runners = [
        {"horse_id": "SYNTH-A", "horse_no": 1, "frame_no": 1,
         "barrier_no": 1, "carried_weight": 55, "history": []},
        {"horse_id": "SYNTH-B", "horse_no": 2, "frame_no": 2,
         "barrier_no": 2, "carried_weight": 55, "history": []},
    ]
    raw = {
        "schema": "prism.engine.raw/v1",
        "mode": "SYNTHETIC",
        "race": {"race_id": "SYNTH-ENGINE-SMOKE", "venue": "TEST",
                 "surface": "TURF", "distance_m": 1600,
                 "direction": "RIGHT", "class_rating": 50,
                 "cutoff": CUTOFF, "barrier_count": 2},
        "runners": runners,
        "source": {"source_id": "SYNTHETIC-TEST-ONLY",
                   "available_at": LOCK, "content_hash": ""},
    }
    raw["source"]["content_hash"] = digest({k: v for k, v in raw.items() if k != "source"})
    return raw

class FullEngineSmoke(unittest.TestCase):
    def test_predict_directly(self):
        output = predict(fixture(), LOCK, config={
            "half_life_days": 180., "cold_start_prior": 50.,
            "score_temperature": 18., "runs": 100, "seed": 42,
            "budget_yen": 500, "max_points": 5, "min_net_ev": 0.,
            "max_quote_age_seconds": 300, "candidate_pool_limit": 20,
            "max_exposure_per_leg": 3, "longshot_odds_min": 10.,
        })
        self.assertEqual(output["race_id"], "SYNTH-ENGINE-SMOKE")
        self.assertEqual(set(output["win"]), {"SYNTH-A", "SYNTH-B"})
        self.assertAlmostEqual(sum(output["win"].values()), 1.)
        self.assertFalse(output["performance_validated"])
        self.assertFalse(output["source_authenticity_verified"])

    def test_synthetic_post_market_and_fixed_100_yen_settlement(self):
        """End-to-end synthetic lock -> candidate -> settlement; not official racing data."""
        lock = predict(fixture(), LOCK, config={
            "half_life_days": 180., "cold_start_prior": 50.,
            "score_temperature": 18., "runs": 100, "seed": 42,
            "budget_yen": 100, "max_points": 1, "min_net_ev": 0.,
            "max_quote_age_seconds": 300, "candidate_pool_limit": 20,
            "max_exposure_per_leg": 3, "longshot_odds_min": 10.,
        })
        market = {
            "race_id": lock["race_id"], "prediction_hash": lock["lock_hash"],
            "observed_at": "2026-11-19T00:01:00+09:00",
            "opened_at": "2026-11-19T00:02:00+09:00",
            "place_slots": 1,
            "quotes": [{"bet_type": "WIN", "legs": ["SYNTH-A"],
                        "odds_low": 10., "odds_high": 10.}],
        }
        post = post_market(lock, market, config={
            "half_life_days": 180., "cold_start_prior": 50.,
            "score_temperature": 18., "runs": 100, "seed": 42,
            "budget_yen": 100, "max_points": 1, "min_net_ev": 0.,
            "max_quote_age_seconds": 300, "candidate_pool_limit": 20,
            "max_exposure_per_leg": 3, "longshot_odds_min": 10.,
        })
        plan = post["plan"]
        self.assertEqual(plan["stake_yen"], 100)
        self.assertEqual(len(plan["tickets"]), 1)
        result = {
            "race_id": lock["race_id"], "prediction_hash": lock["lock_hash"],
            "available_at": "2026-11-20T15:05:00+09:00",
            "payouts": [{"bet_type": "WIN", "legs": ["SYNTH-A"],
                         "payout_per_100_yen": 1000}],
            "refund_keys": [], "complete_bet_types": ["WIN"],
        }
        settled = settle(plan, result, lock["race_id"], lock["cutoff"])
        self.assertEqual(settled["gross_stake_yen"], 100)
        self.assertEqual(settled["payout_yen"], 1000)
        self.assertEqual(settled["profit_yen"], 900)
        self.assertEqual(settled["roi"], 10.0)

    def test_future_source_rejected(self):
        raw = fixture()
        raw["source"]["available_at"] = "2026-11-19T01:00:00+09:00"
        with self.assertRaisesRegex(ValueError, "source unavailable at lock"):
            predict(raw, LOCK)

    def test_source_integrity_mismatch_rejected(self):
        raw = fixture()
        raw["runners"][0]["horse_no"] = 3
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            predict(raw, LOCK)

    def test_history_after_lock_rejected(self):
        raw = fixture()
        raw["runners"][0]["history"] = [{
            "occurred_at": "2026-11-19T00:30:00+09:00",
            "available_at": "2026-11-19T00:31:00+09:00",
            "performance_score": 55,
            "distance_m": 1600,
            "surface": "TURF",
            "direction": "RIGHT",
            "class_rating": 50,
            "venue": "TEST",
        }]
        raw["source"]["content_hash"] = digest({k: v for k, v in raw.items() if k != "source"})
        with self.assertRaisesRegex(ValueError, "history occurred after lock"):
            predict(raw, LOCK)

    def test_after_cutoff_rejected(self):
        with self.assertRaisesRegex(ValueError, "prediction locked after cutoff"):
            predict(fixture(), "2026-11-20T15:01:00+09:00")

if __name__ == "__main__":
    unittest.main()
