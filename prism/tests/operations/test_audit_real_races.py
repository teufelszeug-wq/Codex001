import unittest,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from audit_real_races import audit
TARGET={'targets':[{'race_id':'R1','off_at':'2026-11-15T15:40:00+09:00'}]}
class AuditTest(unittest.TestCase):
 def test_empty_is_critical(self):
  self.assertEqual(audit(TARGET,[])['status'],'CRITICAL')
 def test_backfilled_prediction_not_verified(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'v1.json'
   p.write_text(json.dumps({'race_id':'R1','version':1,'saved_at':'2026-11-15T15:41:00+09:00','off_at':'2026-11-15T15:40:00+09:00','source_refs':['official'],'records':[{'picks':[]}]}))
   self.assertEqual(audit(TARGET,[p])['verified_pre_off_count'],0)
 def test_unproven_timestamp_not_counted(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'v1.json'
   p.write_text(json.dumps({'race_id':'R1','version':1,'saved_at':'2026-11-15T14:00:00+09:00','off_at':'2026-11-15T15:40:00+09:00','source_refs':['official'],'records':[{'picks':[]}]}))
   self.assertEqual(audit(TARGET,[p])['races'][0]['reason'],'TIMESTAMP_PRESENT_BUT_EXTERNAL_PRE_OFF_PROOF_REQUIRED')
if __name__=='__main__':unittest.main()
