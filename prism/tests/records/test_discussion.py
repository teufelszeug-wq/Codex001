"""Only in-memory synthetic records; never write fixtures into a real database."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests/dialogue'))
from test_contracts import make_context, records_fixture
from prism_engine.contracts import digest
from prism_dialogue import review_learning
from prism_records.store import RecordStore
from prism_records.discussion import save_discussion


class DiscussionStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = RecordStore(':memory:'); self.addCleanup(self.store.close)
        self.context = make_context(); self.records = records_fixture(self.context)
        self.horses = {}; self.jockeys = {}
        self.store.add_race(self.context['race_id'], {'mode': 'SYNTHETIC'})
        for row in self.context['roster']:
            h = row['horse_id']; self.horses[h] = self.store.add_horse('synthetic:'+h, '試験馬'+h)
            self.jockeys[h] = self.store.add_jockey('synthetic:rider:'+h, '試験騎手'+h)
            self.store.add_entry(self.context['race_id'], row['horse_no'], self.horses[h],
                                 self.jockeys[h], row['frame_no'])
    def save(self, **kwargs):
        return save_discussion(self.store, self.context, self.records, self.horses, self.jockeys, **kwargs)
    def test_template_keeps_source_zero_assessment(self):
        result = self.save(); self.assertEqual(result['assessment_rows'], 0)
        row = self.store.connection.execute('SELECT payload_json FROM discussions').fetchone()
        self.assertEqual(json.loads(row[0])['records'], self.records)
        self.assertEqual(self.store.summary()['counts']['assessments'], 0)
    def test_simulation_claims_are_not_independent_learning(self):
        self.records['execution_mode'] = 'ROLE_SIMULATION'; result = self.save()
        self.assertGreater(result['assessment_rows'], 0); self.assertEqual(result['actual_verified_assessments'], 0)
        row = self.store.connection.execute('SELECT * FROM assessments LIMIT 1').fetchone()
        self.assertEqual(row['subject_type'], 'HORSE'); self.assertEqual(row['verified_independent'], 0)
        self.assertEqual(json.loads(row['payload_json'])['jockey_relationship'], 'RELATED_RIDER_NOT_DIRECT_ASSESSMENT')
    def test_self_declared_independent_still_unverified(self):
        self.records['execution_mode'] = 'INDEPENDENT_EXECUTION'; self.save()
        self.assertEqual(self.store.connection.execute('SELECT SUM(verified_independent) FROM assessments').fetchone()[0], 0)
    def test_exact_replay_idempotent(self):
        self.records['execution_mode'] = 'ROLE_SIMULATION'
        a = self.save(); before = self.store.summary(); b = self.save()
        self.assertEqual(a['discussion_id'], b['discussion_id']); self.assertEqual(b['inserted_assessment_rows'], 0)
        self.assertEqual(before, self.store.summary())
    def test_missing_horse_or_wrong_entry_rejected_atomically(self):
        self.horses['h1'] = self.horses['h2']
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(self.store.summary()['counts']['discussions'], 0)
    def test_unknown_db_horse_rejected(self):
        self.horses['h1'] = 'not-in-db'
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(self.store.summary()['counts']['discussions'], 0)
    def test_wrong_rider_rejected(self):
        self.jockeys['h1'] = self.jockeys['h2']
        with self.assertRaises(ValueError): self.save()
    def set_db_cutoff(self, cutoff):
        metadata = {'mode': 'SYNTHETIC', 'cutoff': cutoff}
        self.store.connection.execute('UPDATE races SET metadata_json=?,content_hash=? WHERE id=?',
                                      (json.dumps(metadata), digest(metadata), self.context['race_id']))
    def test_known_database_cutoff_must_match(self):
        self.set_db_cutoff('2026-01-01T09:50:00+09:00')
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(self.store.summary()['counts']['discussions'], 0)
    def test_same_instant_offset_is_accepted_without_attestation(self):
        self.set_db_cutoff('2026-01-01T01:00:00Z'); self.save()
        payload = json.loads(self.store.connection.execute('SELECT payload_json FROM discussions').fetchone()[0])
        self.assertEqual(payload['time_provenance']['temporal_class'], 'CUTOFF_MATCHED_NOT_ATTESTED')
        self.assertFalse(payload['time_provenance']['externally_attested'])
    def test_unknown_database_cutoff_cannot_promote_pre_available(self):
        self.context['input_mode'] = 'PRE_AVAILABLE'
        self.context['context_hash'] = digest({k:v for k,v in self.context.items() if k != 'context_hash'})
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(self.store.summary()['counts']['discussions'], 0)
    def test_unknown_historical_cutoff_remains_unknown(self):
        self.context['input_mode'] = 'HISTORICAL_RECONSTRUCTION'
        self.context['context_hash'] = digest({k:v for k,v in self.context.items() if k != 'context_hash'})
        self.save()
        payload = json.loads(self.store.connection.execute('SELECT payload_json FROM discussions').fetchone()[0])
        self.assertEqual(payload['time_provenance']['temporal_class'], 'UNKNOWN_RACE_CUTOFF')
        self.assertFalse(payload['time_provenance']['externally_attested'])
    def test_malformed_discussion_creates_no_records(self):
        self.records['prediction_hash'] = 'other'
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(self.store.summary()['counts']['discussions'], 0)
    def test_post_review_separate_and_pre_unchanged(self):
        self.save()
        pre = tuple(self.store.connection.execute('SELECT * FROM discussions').fetchone())
        result = {'race_id': self.context['race_id'], 'prediction_hash': self.context['prediction_hash'],
                  'available_at': '2026-01-01T10:10:00+09:00', 'winners': ['h1']}
        result['content_hash'] = digest(result)
        review = review_learning(self.context, self.records, result)
        saved = self.save(review=review)
        self.assertIsNotNone(saved['post_review_id'])
        self.assertEqual(tuple(self.store.connection.execute("SELECT * FROM discussions WHERE phase='PRE'").fetchone()), pre)
        self.assertEqual(self.store.summary()['counts']['discussions'], 2)
    def test_review_wrong_prediction_or_learning_claim_rejected(self):
        result = {'race_id': self.context['race_id'], 'prediction_hash': self.context['prediction_hash'],
                  'available_at': '2026-01-01T10:10:00+09:00', 'winners': ['h1']}
        result['content_hash'] = digest(result)
        review = review_learning(self.context, self.records, result)
        review['training_achievement_verified'] = True
        review['review_hash'] = digest({k:v for k,v in review.items() if k != 'review_hash'})
        with self.assertRaises(ValueError): self.save(review=review)
        self.assertEqual(self.store.summary()['counts']['discussions'], 0)
    def test_explicit_jockey_subject_is_distinct(self):
        self.records['execution_mode'] = 'ROLE_SIMULATION'
        turn = next(t['turn_id'] for t in self.records['turns'] if t['stage'] == 'FINAL')
        saved = self.save(jockey_subject_turn_ids=[turn])
        row = self.store.connection.execute("SELECT * FROM assessments WHERE subject_type='JOCKEY'").fetchone()
        self.assertEqual(row['turn_id'], turn); self.assertFalse(json.loads(row['payload_json'])['semantic_subject_verified'])
        with self.assertRaises(ValueError): self.save()
        self.assertEqual(self.store.summary()['counts']['assessments'], saved['assessment_rows'])
    def test_explicit_rio_selection_persisted_only_on_final(self):
        self.records['execution_mode'] = 'ROLE_SIMULATION'
        turn = next(t for t in self.records['turns'] if t['agent_id'] == 'RIO' and t['stage'] == 'FINAL')
        selection = {k: turn[k] for k in ('agent_id', 'horse_id', 'turn_id')} | {'selection': 'TOP_PICK'}
        self.records['selections'] = [selection]; self.save()
        claims = [json.loads(r[0]) for r in self.store.connection.execute('SELECT payload_json FROM assessments')]
        selected = [c for c in claims if c['selection'] is not None]
        self.assertEqual(len(selected), 1); self.assertEqual(selected[0]['selection'], selection)
        self.assertEqual(selected[0]['execution_mode'], 'ROLE_SIMULATION')
        self.assertFalse(selected[0]['verified_independent'])
    def test_text_only_top_pick_is_never_persisted_as_selection(self):
        self.records['execution_mode'] = 'ROLE_SIMULATION'
        self.records['turns'][-1]['text'] = 'この馬を本命にします。'; self.save()
        claims = [json.loads(r[0]) for r in self.store.connection.execute('SELECT payload_json FROM assessments')]
        self.assertTrue(all(c['selection'] is None for c in claims))
    def test_jockey_assignment_requires_mapping_and_valid_turn(self):
        self.records['execution_mode'] = 'ROLE_SIMULATION'
        with self.assertRaises(ValueError): self.save(jockey_subject_turn_ids=['unknown'])
        turn = next(t['turn_id'] for t in self.records['turns'] if t['stage'] == 'FINAL')
        with self.assertRaises(ValueError):
            save_discussion(self.store, self.context, self.records, self.horses, jockey_subject_turn_ids=[turn])


if __name__ == '__main__': unittest.main()
