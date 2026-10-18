from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from prism_engine.adapters import normalize
from prism_engine import predict
from fixture import observations_fixture,seal

class AdapterTests(unittest.TestCase):
    def test_past_rank_normalized(self):
        raw,audit=normalize(observations_fixture());self.assertEqual(raw['runners'][0]['history'][0]['performance_score'],100)
        self.assertNotIn('finish_position',raw['runners'][0]['history'][0]);self.assertFalse(audit['source_authenticity_verified'])
    def test_measured_signals_normalized(self):
        raw,_=normalize(observations_fixture())
        self.assertGreater(raw['runners'][0]['workout']['score'],50);self.assertGreater(raw['runners'][0]['jockey']['score'],50)
        self.assertIn('score',raw['runners'][0]['condition'])
    def test_target_results_rejected(self):
        raw=observations_fixture();raw['results']=[];seal(raw)
        with self.assertRaises(ValueError):normalize(raw)
    def test_future_past_observation_rejected(self):
        raw=observations_fixture();raw['runners'][0]['history'][0]['occurred_at']='2026-01-02T01:00:00Z';seal(raw)
        with self.assertRaises(ValueError):normalize(raw)
    def test_raw_hash_tampering_rejected(self):
        raw=observations_fixture();raw['runners'][0]['workout']['time_s']=1
        with self.assertRaises(ValueError):normalize(raw)
    def test_impossible_jockey_counts_rejected(self):
        raw=observations_fixture();raw['runners'][0]['jockey']['wins']=101;seal(raw)
        with self.assertRaises(ValueError):normalize(raw)
