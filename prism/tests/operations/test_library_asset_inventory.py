import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ASSET=ROOT/'data/recovery/library_asset_inventory_20261112.json'

class TestLibraryAssetInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads(ASSET.read_text(encoding='utf-8'))
    def test_unique_asset_ids_and_titles(self):
        assets=self.doc['assets']
        self.assertEqual(len({x['library_file_id'] for x in assets}),len(assets))
        self.assertEqual(len({x['title'] for x in assets}),len(assets))
        self.assertEqual(len(assets),self.doc['summary']['library_assets_identified'])
    def test_no_unsupported_live_promotion(self):
        self.assertFalse(self.doc['policy']['promote_to_live_forecasts'])
        for asset in self.doc['assets']:
            self.assertIsNone(asset['saved_at'])
            self.assertIsNone(asset['race_id'])
            self.assertIn('NOT_IMPORTED',asset['status'])
    def test_consumers_explicit(self):
        for asset in self.doc['assets']:
            self.assertTrue(asset['use_by'])
            self.assertTrue(asset['source']=='Library')

if __name__=='__main__':unittest.main()
