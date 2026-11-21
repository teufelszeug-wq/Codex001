"""Bridge/store regression: complete probabilities and source retrieval provenance."""
import tempfile
import unittest
from pathlib import Path
from prism.racecard_forecast_bridge import build_preday_records
from prism.preday_batch_store import persist_preday_batch

def card():
    return {"race_id":"fixture-20261122-11","source_id":"verified-fixture",
            "source_authenticity_verified":True,
            "scheduled_start_at":"2026-11-22T15:00:00+09:00",
            "source_retrieved_at":"2026-11-21T09:00:00+09:00",
            "horses":[{"horse_id":"h1","horse_name":"試験馬一"},
                      {"horse_id":"h2","horse_name":"試験馬二"}]}

STAMP="2026-11-21T10:00:00+09:00"

def build(predictions):
    return build_preday_records(card(), predictions, forecaster_id="editorial",
                                version="preday-v1", saved_at=STAMP)

class BridgeStoreContractTests(unittest.TestCase):
    def test_retrieval_timestamp_preserved_and_persisted(self):
        rows=build([{"horse_id":"h1","prediction":{"win_probability":0.6}},
                    {"horse_id":"h2","prediction":{"win_probability":0.4}}])
        self.assertTrue(all(r["source_retrieved_at"]==card()["source_retrieved_at"] for r in rows))
        with tempfile.TemporaryDirectory() as d:
            target=Path(persist_preday_batch(rows,d))
            self.assertTrue(target.is_file())
            self.assertIn("source_retrieved_at",target.read_text(encoding="utf-8"))
    def test_scalar_predictions_rejected_at_bridge(self):
        with self.assertRaises(ValueError):
            build([{"horse_id":"h1","prediction":0.6},{"horse_id":"h2","prediction":0.4}])
    def test_missing_probability_rejected_at_bridge(self):
        with self.assertRaisesRegex(ValueError,"win_probability"):
            build([{"horse_id":"h1","prediction":{"rank":1}},
                   {"horse_id":"h2","prediction":{"win_probability":1.0}}])
    def test_source_after_saved_rejected(self):
        c=card()
        c["source_retrieved_at"]="2026-11-21T11:00:00+09:00"
        with self.assertRaises(ValueError):
            build_preday_records(c,[{"horse_id":"h1","prediction":{"win_probability":0.5}},
                                    {"horse_id":"h2","prediction":{"win_probability":0.5}}],
                                  forecaster_id="editorial",version="preday-v1",saved_at=STAMP)

if __name__=="__main__":
    unittest.main()
