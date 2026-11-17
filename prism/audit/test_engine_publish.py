"""Synthetic integration tests; never count these as real-race forecasts."""
import tempfile
import unittest
from pathlib import Path
from prism.audit.engine_publish import publish_engine_lock

CARD = {"schema":"prism.official_racecard/v1","source_verified":True,"race_id":"TEST-001",
"off_at":"2026-11-18T10:00:00+09:00","active_runners":[
{"horse_id":"H1","horse_name":"架空馬甲"},{"horse_id":"H2","horse_name":"架空馬乙"}]}
LOCK = {"schema":"prism.engine.prediction/v1","race_id":"TEST-001",
"cutoff":"2026-11-18T10:00:00+09:00","win":{"H1":0.6,"H2":0.4},
"scores":{"H1":1.0,"H2":0.5},"lock_hash":"abc","input_hash":"def","model_version":"test"}
KW = {"predictor_id":"engine","version":"eve-v1","source":"synthetic-test",
"evidence":[{"available_at":"2026-11-17T09:00:00+09:00"}],
"saved_at":"2026-11-17T10:00:00+09:00","now":"2026-11-17T10:01:00+09:00"}

class EnginePublishTests(unittest.TestCase):
    def test_publish(self):
        with tempfile.TemporaryDirectory() as d:
            p=publish_engine_lock(d,CARD,LOCK,**KW)
            self.assertTrue(p.exists())
            self.assertEqual(len(list(Path(d).glob("*.batch.json"))),1)
    def test_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            publish_engine_lock(d,CARD,LOCK,**KW)
            with self.assertRaises(FileExistsError):
                publish_engine_lock(d,CARD,LOCK,**KW)
    def test_missing_prediction(self):
        with tempfile.TemporaryDirectory() as d:
            bad=dict(LOCK,win={"H1":1.0})
            with self.assertRaises(ValueError):
                publish_engine_lock(d,CARD,bad,**KW)
            self.assertFalse(list(Path(d).iterdir()))
    def test_future_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            bad=dict(KW,evidence=[{"available_at":"2026-11-17T11:00:00+09:00"}])
            with self.assertRaises(ValueError):
                publish_engine_lock(d,CARD,LOCK,**bad)
    def test_post_race(self):
        with tempfile.TemporaryDirectory() as d:
            bad=dict(KW,now="2026-11-18T10:01:00+09:00")
            with self.assertRaises(ValueError):
                publish_engine_lock(d,CARD,LOCK,**bad)

if __name__=="__main__":
    unittest.main()
