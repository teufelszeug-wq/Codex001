from pathlib import Path
import sqlite3
import tempfile
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from prism_records import RecordStore
from prism_records.updates import SourceUpdates


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.store = RecordStore(':memory:')
        self.horse = self.store.add_horse('official:1', '同名')
        self.other = self.store.add_horse('official:2', '同名')
        self.jockey = self.store.add_jockey('rider:1', '騎手')
        self.store.add_race('race', {'cutoff': '2026-01-02T12:00:00+09:00'})
        self.store.add_entry('race', 1, self.horse, self.jockey)
        self.store.add_entry('race', 2, self.other)
        self.updates = SourceUpdates(self.store)

    def tearDown(self): self.store.close()

    def append(self, **kwargs):
        args = dict(subject_type='HORSE', entity_id=self.horse, race_id='race',
                    fact_key='workout', payload={'seconds': 52}, source_ref='official:workout',
                    schema_id='workout/v1', recorded_at='2026-01-02T10:00:00+09:00',
                    available_at='2026-01-02T09:00:00+09:00', temporal_class='PRE_AVAILABLE', phase='PRE')
        args.update(kwargs)
        return self.updates.append(**args)

    def test_cache_hit_has_no_duplicate_observation(self):
        first = self.append()
        self.assertEqual(self.append(recorded_at='2026-01-02T11:00:00+09:00')['status'], 'CACHE_HIT')
        self.assertIn('#prism-version=', first['version']['versioned_source_ref'])
        self.assertEqual(self.store.summary()['counts']['observations'], 1)

    def test_changed_source_version_retires_without_rewriting(self):
        old = self.append()['version']
        new = self.append(payload={'seconds': 51}, recorded_at='2026-01-02T11:00:00+09:00',
                          available_at='2026-01-02T10:30:00+09:00', prior_id=old['id'], correction=True)
        self.assertTrue(new['changed'])
        self.assertEqual(new['changes']['seconds']['before'], 52)
        self.assertEqual(new['changes']['seconds']['after'], 51)
        self.assertEqual(new['retired_version_id'], old['id'])
        past = self.updates.current('HORSE', self.horse, 'race', 'workout', as_of='2026-01-02T10:15:00+09:00')
        now = self.updates.current('HORSE', self.horse, 'race', 'workout', as_of='2026-01-02T11:15:00+09:00')
        self.assertEqual(past[0]['payload']['seconds'], 52)
        self.assertEqual(now[0]['payload']['seconds'], 51)
        self.assertEqual(self.store.summary()['counts']['observations'], 2)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.conn.execute('DELETE FROM entity_fact_versions WHERE id=?', (old['id'],))

    def test_conflicting_source_held_and_does_not_retire(self):
        old = self.append()['version']
        conflict = self.append(source_ref='different:source', payload={'seconds': 40})
        self.assertEqual(conflict['status'], 'PENDING_CONFLICT')
        self.assertIsNone(conflict['retired_version_id'])
        self.assertIsNone(conflict['version']['observation_id'])
        self.assertEqual(self.store.summary()['counts']['observations'], 1)
        self.assertEqual(conflict['conflicting_version_ids'], [old['id']])
        self.assertEqual(self.updates.current('HORSE', self.horse, 'race', 'workout',
                                            as_of='2026-01-02T11:00:00+09:00')[0]['id'], old['id'])

    def test_same_name_does_not_merge_and_prior_is_subject_bound(self):
        prior = self.append()['version']['id']
        with self.assertRaises(ValueError): self.append(entity_id=self.other, prior_id=prior)
        other = self.append(entity_id=self.other)
        self.assertEqual(other['status'], 'ACCEPTED')
        self.assertNotEqual(other['version']['entity_id'], self.horse)

    def test_jockey_facts_have_independent_identity(self):
        fact = self.append(subject_type='JOCKEY', entity_id=self.jockey, fact_key='jockey_sample',
                           schema_id='jockey/v1', payload={'rides': 12, 'wins': 2})
        self.assertIsNone(fact['version']['observation_id'])
        self.assertEqual(self.updates.current('JOCKEY', self.jockey, 'race', 'jockey_sample',
                         as_of='2026-01-02T11:00:00+09:00')[0]['payload']['rides'], 12)
        with self.assertRaises(ValueError):
            self.append(subject_type='JOCKEY', entity_id=self.jockey, payload={'jockey_id': self.horse})
        with self.assertRaises(ValueError):
            self.append(subject_type='JOCKEY', entity_id=self.jockey,
                        payload={'jockey_identity': {'source_key': 'different:rider'}})

    def test_unknown_never_promoted_and_not_selected_as_known(self):
        old = self.append(phase='UNKNOWN', available_at=None, temporal_class='UNKNOWN_TIMESTAMP')['version']
        self.assertEqual(self.updates.current('HORSE', self.horse, 'race', 'workout',
                                             as_of='2026-01-02T11:00:00+09:00'), [])
        with self.assertRaises(ValueError): self.append(prior_id=old['id'])
        with self.assertRaises(ValueError): self.append()

    def test_nested_results_and_time_identity_rejected_atomically(self):
        for change in ({'payload': {'history': {'official_result': 1}}},
                       {'payload': {'history': {'available_at': None}}},
                       {'payload': {'horse_id': self.other}},
                       {'payload': {'schema': 'wrong/v1'}},
                       {'payload': {'review_status': 'REJECTED'}},
                       {'payload': {'jockey_id': 'wrong:rider'}},
                       {'fact_key': 'history.official_result', 'payload': {'value': 1}},
                       {'available_at': '2026-01-02T13:00:00+09:00'},
                       {'recorded_at': '2026-01-02T08:00:00+09:00'}):
            with self.subTest(change=change), self.assertRaises(ValueError): self.append(**change)
        self.assertEqual(self.store.summary()['counts']['observations'], 0)

    def test_retired_prior_cannot_fork_correction(self):
        old = self.append()['version']['id']
        self.append(payload={'seconds': 51}, prior_id=old)
        with self.assertRaises(ValueError): self.append(payload={'seconds': 50}, prior_id=old)

    def test_read_only_reader_existing_ledger_and_cached_append_rejected(self):
        self.append()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'facts.sqlite'
            target = sqlite3.connect(path)
            self.store.conn.backup(target)
            target.close()
            reader = RecordStore(path, read_only=True)
            try:
                updates = SourceUpdates(reader)
                self.assertEqual(len(updates.current('HORSE', self.horse, 'race', 'workout',
                                                     as_of='2026-01-02T11:00:00+09:00')), 1)
                original = self.updates
                self.updates = updates
                try:
                    with self.assertRaisesRegex(ValueError, 'writable'): self.append()
                finally: self.updates = original
            finally: reader.close()

    def test_read_only_reader_without_ledger_is_empty_and_does_not_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'legacy.sqlite'
            creator = RecordStore(path)
            creator.close()
            reader = RecordStore(path, read_only=True)
            try:
                updates = SourceUpdates(reader)
                self.assertEqual(updates.history('HORSE', 'h', 'r', 'f'), [])
                self.assertEqual(updates.current('HORSE', 'h', 'r', 'f',
                                                 as_of='2026-01-02T11:00:00+09:00'), [])
                self.assertFalse(updates._has_schema())
            finally: reader.close()

    def test_same_value_other_source_is_not_implicitly_retired(self):
        first = self.append()['version']['id']
        second = self.append(source_ref='source:corroboration')['version']['id']
        self.assertEqual(len(self.updates.current('HORSE', self.horse, 'race', 'workout',
                                                 as_of='2026-01-02T11:00:00+09:00')), 2)
        conflict = self.append(payload={'seconds': 51})
        self.assertEqual(conflict['status'], 'PENDING_CONFLICT')
        self.assertEqual(conflict['conflicting_version_ids'], [second])
        self.assertEqual({r['id'] for r in self.updates.current('HORSE', self.horse, 'race', 'workout',
                         as_of='2026-01-02T11:00:00+09:00')}, {first, second})


if __name__ == '__main__': unittest.main()
