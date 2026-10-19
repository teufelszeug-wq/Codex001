"""Synthetic, read-only profile lookup checks."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from prism_records import RecordStore
from query_entity_database import query


class QueryTests(unittest.TestCase):
    def test_profiles_and_literal_name_search_do_not_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'records.sqlite'
            store = RecordStore(path)
            horse = store.add_horse('TEST_H1', 'SYNTHETIC_%Horse')
            jockey = store.add_jockey('TEST_J1', 'SYNTHETIC Rider')
            store.add_race('TEST_R1', {'mode': 'SYNTHETIC'})
            store.add_entry('TEST_R1', 4, horse, jockey, 2)
            store.close()
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(query(path)['counts']['horses'], 1)
            result = query(path, 'horse', search='_%')
            self.assertEqual(result['matches'][0]['id'], horse)
            self.assertEqual(query(path, 'horse', entity_id=horse)['entries'][0]['horse_no'], 4)
            self.assertEqual(query(path, 'jockey', entity_id=jockey)['entity']['display_name'], 'SYNTHETIC Rider')
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing.sqlite'
            with self.assertRaises(Exception): query(path)
            self.assertFalse(path.exists())

    def test_bad_query_options(self):
        for args in [dict(kind='bad'), dict(limit=0), dict(search='x'), dict(kind='horse',search='x',entity_id='y'),
                     dict(agent_id='RIO'), dict(kind='jockey',entity_id='j',agent_id='RIO',as_of='2026-01-01T00:00:00Z')]:
            with self.assertRaises(ValueError): query('unused.sqlite', **args)

    def test_agent_memory_reuses_data_without_inventing_rio_pick(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'records.sqlite'
            store = RecordStore(path)
            horse = store.add_horse('TEST_H1', 'SYNTHETIC Horse')
            store.add_race('TEST_R1', {'cutoff': '2026-01-01T10:00:00+09:00'})
            store.add_entry('TEST_R1', 1, horse, frame_no=1)
            store.close()
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            out = query(path, 'horse', entity_id=horse, agent_id='RIO', as_of='2026-01-02T10:00:00+09:00')
            memory = out['agent_memory']
            self.assertTrue(memory['familiarity']['prohibit_first_meeting_claim'])
            self.assertTrue(memory['familiarity']['prohibit_invented_past_endorsement'])
            self.assertEqual(memory['past_top_picks_count'], 0)
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())
