from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from b0_input_gate import validate
import test_b0_gate_legacy as legacy_fixture
from run_core_engine import run
from prism_engine import predict
from fixture import raw_fixture,market_fixture,calibration_fixture

LOCK='2026-01-01T09:55:00+09:00'

class CliAndGateTests(unittest.TestCase):
    def test_b0_actual_evaluator_fields_are_rejected(self):
        for level in ('race','runner','provenance'):
            for field in ('results','win_payouts','unknown_extra'):
                raw=legacy_fixture.RecoveryTests().fixture()
                obj=raw['races'][0] if level=='race' else raw['races'][0]['runners'][0]
                if level=='provenance':obj=obj['provenance']
                obj[field]={}
                with self.subTest(level=level,field=field):self.assertEqual(validate(raw)['status'],'BLOCKED')
    def test_bundle_replay_immutable(self):
        raw=raw_fixture();cal=calibration_fixture();lock=predict(raw,LOCK,calibration=cal);market=market_fixture(lock)
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'out';first=run(raw,market,LOCK,directory,calibration=cal)
            again=run(raw,market,LOCK,directory,calibration=cal);self.assertEqual(first,again)
            market['quotes'][0]['odds_high']+=1
            with self.assertRaisesRegex(ValueError,'overwrite'):run(raw,market,LOCK,directory,calibration=cal)
    def test_bad_input_produces_no_bundle(self):
        raw=raw_fixture();lock=predict(raw,LOCK);market=market_fixture(lock);market['prediction_hash']='bad'
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'out'
            with self.assertRaises(ValueError):run(raw,market,LOCK,directory)
            self.assertFalse(directory.exists())

if __name__=='__main__':unittest.main()
