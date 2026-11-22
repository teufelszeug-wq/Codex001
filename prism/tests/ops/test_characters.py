from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from prism_ops.characters import build_character_snapshot, get_character, verify_character, verify_character_snapshot


def snapshot_fixture():
    return build_character_snapshot([
        {'agent_id': 'notion-ability', 'name': '正本テスト担当', 'role': 'specialist',
         'configuration': {'specialty': '能力評価', 'instruction': '出典を明示'},
         'source_page_url': 'https://www.notion.so/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'}],
        source_url='https://www.notion.so/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        captured_at='2026-11-13T00:00:00+00:00')


class CharactersTests(unittest.TestCase):
    def test_frozen_snapshot_and_selected_character(self):
        snapshot = snapshot_fixture()
        self.assertTrue(verify_character_snapshot(snapshot))
        character = get_character(snapshot, 'notion-ability')
        self.assertTrue(verify_character(character))
        self.assertEqual(character['character_snapshot_hash'], snapshot['snapshot_hash'])
        character['configuration']['specialty'] = 'changed'
        with self.assertRaises(ValueError):
            verify_character(character)
        self.assertEqual(snapshot['records'][0]['configuration']['specialty'], '能力評価')

    def test_does_not_invent_unknown_character(self):
        with self.assertRaises(ValueError):
            get_character(snapshot_fixture(), 'made-up')

    def test_rejects_missing_or_non_notion_canonical_settings(self):
        snapshot = snapshot_fixture()
        for key, value in [('configuration', {}), ('source_page_url', 'https://example.com/config')]:
            records = deepcopy(snapshot['records'])
            records[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_character_snapshot(records, source_url=snapshot['source_url'], captured_at=snapshot['captured_at'])
        with self.assertRaises(ValueError):
            build_character_snapshot(snapshot['records'], source_url=snapshot['source_url'], captured_at='2026-11-13T00:00:00')

    def test_duplicate_and_tampered_records_rejected(self):
        snapshot = snapshot_fixture()
        with self.assertRaises(ValueError):
            build_character_snapshot(snapshot['records'] * 2, source_url=snapshot['source_url'], captured_at=snapshot['captured_at'])
        snapshot['records'][0]['name'] = 'silently renamed'
        with self.assertRaises(ValueError):
            verify_character_snapshot(snapshot)


if __name__ == '__main__':
    unittest.main()
