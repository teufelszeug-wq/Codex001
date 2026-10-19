"""Synthetic, in-memory pre-discussion DB loading integration."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests/engine'))
from fixture import raw_fixture
from prism_engine import predict
from prism_engine.contracts import digest
from prism_records.store import RecordStore
from prism_records.memory import prepare_race_memory
from prism_dialogue import build_discussion_context, validate_discussion
from test_contracts import records_fixture


class MemoryContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = raw_fixture()
        cls.prediction = predict(cls.raw, '2026-01-01T09:55:00+09:00')

    def setUp(self):
        self.store = RecordStore(':memory:'); self.addCleanup(self.store.close)
        self.store.add_race(self.raw['race']['race_id'], self.raw['race'])
        for runner in self.raw['runners']:
            horse = self.store.add_horse('synthetic:' + runner['horse_id'], '試験' + runner['horse_id'])
            self.store.add_entry(self.raw['race']['race_id'], runner['horse_no'], horse, frame_no=runner['frame_no'])
        self.bundle = {'schema': 'prism.engine.bundle/v1', 'prediction': deepcopy(self.prediction), 'raw': deepcopy(self.raw)}
        self.memory = prepare_race_memory(self.store, self.raw['race']['race_id'],
                                          '2026-01-01T09:54:00+09:00', ['RIO'])

    def test_memory_added_without_changing_probabilities_or_bundle(self):
        before = digest(self.bundle)
        context = build_discussion_context(self.bundle, self.memory)
        self.assertEqual(before, digest(self.bundle))
        self.assertEqual(context['win'], self.prediction['win'])
        self.assertEqual(context['records_memory'], self.memory)
        self.assertEqual(set(context['memory_horse_map']), set(self.prediction['win']))
        self.assertEqual(context['evidence'][-1]['evidence_id'], 'memory:' + self.memory['snapshot_hash'])
        self.assertFalse(context['source_authenticity_verified'])

    def test_no_memory_remains_backward_compatible(self):
        a = build_discussion_context(self.bundle)
        b = build_discussion_context(self.bundle, None)
        self.assertEqual(a, b); self.assertNotIn('records_memory', a)

    def test_memory_snapshot_can_be_cited_in_structural_dialogue(self):
        context = build_discussion_context(self.bundle, self.memory)
        records = records_fixture(context)
        records['turns'][0]['evidence_refs'] = ['memory:' + self.memory['snapshot_hash']]
        audit = validate_discussion(context, records)
        self.assertEqual(audit['status'], 'STRUCTURAL_PASS', audit['errors'])
        self.assertEqual(audit['counts']['verified_independent_sessions'], 0)

    def test_memory_after_prediction_lock_rejected(self):
        memory = prepare_race_memory(self.store, self.raw['race']['race_id'],
                                      '2026-01-01T09:56:00+09:00', ['RIO'])
        with self.assertRaises(ValueError): build_discussion_context(self.bundle, memory)

    def test_wrong_frame_or_number_rejected_even_resealed(self):
        for field in ('horse_no', 'frame_no'):
            memory = deepcopy(self.memory); memory['runners'][0][field] = 8
            memory['snapshot_hash'] = digest({k:v for k,v in memory.items() if k != 'snapshot_hash'})
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_discussion_context(self.bundle, memory)

    def test_tampered_memory_rejected(self):
        memory = deepcopy(self.memory); memory['race_id'] = 'OTHER'
        with self.assertRaises(ValueError): build_discussion_context(self.bundle, memory)


if __name__ == '__main__': unittest.main()
