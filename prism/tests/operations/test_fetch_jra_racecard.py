import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from fetch_jra_racecard import extract_jra_rows,fetch_jra

class TestJraFetcher(unittest.TestCase):
    def test_explicit_horse_numbers(self):
        html='<table><tr><th>枠</th><th>馬番</th><th>馬名</th><th>性齢</th></tr><tr><td>1</td><td>2</td><td>架空馬B 厩舎</td><td>牡3</td></tr><tr><td>1</td><td>1</td><td>架空馬A 厩舎</td><td>牝3</td></tr></table>'
        self.assertEqual([r['horse_no'] for r in extract_jra_rows(html)],[1,2])
    def test_fail_closed_without_numbers(self):
        with self.assertRaisesRegex(ValueError,'cannot reliably'):
            extract_jra_rows('<table><tr><td>馬名</td><td>架空馬</td></tr></table>')
    def test_off_domain_rejected_before_network(self):
        with self.assertRaisesRegex(ValueError,'official'):
            fetch_jra('https://example.com/JRADB/accessD.html')

if __name__=='__main__':unittest.main()
