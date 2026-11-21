"""Synthetic regressions for Thursday entries before the official draw."""
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fixture import raw_fixture, observations_fixture, seal
from prism_engine import predict
from prism_engine.adapters import normalize
from prism_engine.contracts import validate


def undrawn(raw):
    raw['schema']=raw['schema'].replace('/v1','/v2')
    raw['race']['declaration_stage']='ENTRIES_CONFIRMED'
    for runner in raw['runners']:
        runner.update(horse_no=None,frame_no=None,barrier_no=None)
    return seal(raw)


class TestDeclarationStage(unittest.TestCase):
    def test_entries_predict_without_inventing_draw_numbers(self):
        raw=undrawn(raw_fixture())
        lock=predict(raw,'2026-01-01T09:30:00+09:00')
        self.assertEqual(set(lock['win']),{r['horse_id'] for r in raw['runners']})
        self.assertAlmostEqual(sum(lock['win'].values()),1.)
        self.assertEqual(lock['declaration_stage'],'ENTRIES_CONFIRMED')
        self.assertTrue(all(frame is None for frame in lock['frames'].values()))
        for row in lock['features']['horses'].values():
            self.assertIsNone(row['horse_no'])
            self.assertIsNone(row['frame_no'])
            self.assertIsNone(row['barrier_no'])
            self.assertIsNone(row['components']['bias_tbi_ssi'])
            self.assertEqual(row['availability']['bias_tbi_ssi'],'UNAVAILABLE')

    def test_entry_order_does_not_change_predictions(self):
        raw=undrawn(raw_fixture())
        reordered=deepcopy(raw);reordered['runners'].reverse();seal(reordered)
        first=predict(raw,'2026-01-01T09:30:00+09:00')
        second=predict(reordered,'2026-01-01T09:30:00+09:00')
        self.assertEqual(first['win'],second['win'])
        self.assertEqual(first['scores'],second['scores'])

    def test_draw_requires_numbers_and_frames(self):
        for field in ('horse_no','frame_no','barrier_no'):
            raw=raw_fixture();raw['schema']='prism.engine.raw/v2'
            raw['race']['declaration_stage']='DRAW_CONFIRMED'
            raw['runners'][0][field]=None;seal(raw)
            with self.subTest(field=field),self.assertRaises(ValueError):validate(raw)

    def test_duplicate_identity_still_rejected_without_numbers(self):
        raw=undrawn(raw_fixture());raw['runners'][1]['horse_id']='h1';seal(raw)
        with self.assertRaisesRegex(ValueError,'identity ambiguous'):validate(raw)

    def test_observation_v2_normalizes_without_a_draw(self):
        raw,_=normalize(undrawn(observations_fixture()))
        self.assertEqual(raw['schema'],'prism.engine.raw/v2')
        self.assertEqual(raw['race']['declaration_stage'],'ENTRIES_CONFIRMED')
        self.assertIsNone(raw['runners'][0]['horse_no'])
        predict(raw,'2026-01-01T09:30:00+09:00')

    def test_v1_remains_strict(self):
        raw=raw_fixture();raw['runners'][0]['horse_no']=None;seal(raw)
        with self.assertRaises(ValueError):validate(raw)
        raw=raw_fixture();raw['race']['declaration_stage']='DRAW_CONFIRMED';seal(raw)
        with self.assertRaises(ValueError):validate(raw)


if __name__=='__main__':unittest.main()
