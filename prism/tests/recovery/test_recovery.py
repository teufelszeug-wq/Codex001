import copy
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from recover_local_zip import recover
from b0_input_gate import validate

class RecoveryTests(unittest.TestCase):
    def archive(self,name='a.txt'):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:z.writestr(name,'verified content')
        return stream.getvalue().split(b'PK\x01\x02')[0]
    def test_missing_directory_recovers_without_complete_claim(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'broken.zip';p.write_bytes(self.archive());out=Path(d)/'out'
            r=recover(p,out);self.assertEqual(r['verified_entries'],1)
            self.assertFalse(r['archive_complete']);self.assertEqual((out/'a.txt').read_text(),'verified content')
            self.assertEqual(recover(p,out),r)
    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes(self.archive('../escape'))
            with self.assertRaises(ValueError):recover(p,Path(d)/'out')
    def test_truncation_does_not_write_partial_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes(self.archive()[:-2]);out=Path(d)/'out'
            self.assertEqual(recover(p,out)['verified_entries'],0);self.assertEqual(list(out.iterdir()),[])
    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';p.write_bytes(self.archive())
            with self.assertRaises(ValueError):recover(p,Path(d)/'out',max_entry=2)
    def fixture(self):
        provenance={'temporal_class':'PRE_AVAILABLE','source_id':'synthetic','content_hash':'a'*64,'available_at':'2026-01-01T09:00:00+09:00'}
        runner={'race_id':'test1','runner_key':'h1','horse_no':1,'frame_no':1,'carried_weight':55,'identity_status':'RESOLVED','provenance':provenance.copy()}
        return {'races':[{'race_id':'test1','authority':'TEST','date':'20260101','venue':'test','race_no':1,'surface':'DIRT','distance':1200,'cutoff':'2026-01-01T10:00:00+09:00','provenance':provenance,'runners':[runner]}]}
    def test_valid_input_and_deterministic_hash(self):
        d=self.fixture();a=validate(d);self.assertEqual(a['status'],'INPUT_STRUCTURE_PASS')
        self.assertEqual(a,validate(copy.deepcopy(d)));self.assertFalse(a['b0_reproduced'])
    def test_unknown_and_future_time_blocked(self):
        for change in ({'temporal_class':'UNKNOWN_TIMESTAMP'},{'available_at':'2026-01-02T10:00:00+09:00'}):
            d=self.fixture();d['races'][0]['runners'][0]['provenance'].update(change)
            self.assertEqual(validate(d)['status'],'BLOCKED')
    def test_nested_result_and_market_blocked(self):
        for key in ('finish_position','odds'):
            d=self.fixture();d['races'][0]['runners'][0]['extra']={key:1}
            self.assertEqual(validate(d)['status'],'BLOCKED')
    def test_duplicate_and_ambiguous_runner_blocked(self):
        d=self.fixture();d['races'][0]['runners']*=2;self.assertEqual(validate(d)['status'],'BLOCKED')
        d=self.fixture();d['races'][0]['runners'][0]['identity_status']='AMBIGUOUS_ID';self.assertEqual(validate(d)['status'],'BLOCKED')

if __name__=='__main__':unittest.main()
