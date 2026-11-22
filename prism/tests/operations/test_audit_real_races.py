import unittest,sys,tempfile,json,subprocess
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
   p.write_text(json.dumps({'race_id':'R1','version':1,'saved_at':'2026-11-15T15:41:00+09:00','off_at':'2026-11-15T15:40:00+09:00','source_refs':['official'],'records':[{'forecaster_id':'HONSHI','picks':[]}]}))
   self.assertEqual(audit(TARGET,[p])['verified_pre_off_count'],0)
 def test_unproven_timestamp_not_counted(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'v1.json'
   p.write_text(json.dumps({'race_id':'R1','version':1,'saved_at':'2026-11-15T14:00:00+09:00','off_at':'2026-11-15T15:40:00+09:00','source_refs':['official'],'records':[{'forecaster_id':'HONSHI','picks':[]}]}))
   self.assertEqual(audit(TARGET,[p])['races'][0]['reason'],'PRE_OFF_CANDIDATE_AWAITING_GIT_OR_STORAGE_HISTORY')
 def test_git_commit_after_off_not_verified(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   subprocess.run(['git','init',str(root)],check=True,capture_output=True)
   subprocess.run(['git','-C',d,'config','user.email','test@example.invalid'],check=True)
   subprocess.run(['git','-C',d,'config','user.name','Test'],check=True)
   p=root/'v1.json'
   p.write_text(json.dumps({'race_id':'R1','version':1,'saved_at':'2026-11-15T14:00:00+09:00','off_at':'2026-11-15T15:40:00+09:00','source_refs':['official'],'records':[{'forecaster_id':'HONSHI','picks':[]}]}))
   subprocess.run(['git','-C',d,'add','v1.json'],check=True)
   subprocess.run(['git','-C',d,'commit','-m','late'],check=True,capture_output=True)
   result=audit(TARGET,[p],root)
   self.assertEqual(result['verified_pre_off_count'],0)
   self.assertEqual(result['pre_off_candidate_count'],1)
if __name__=='__main__':unittest.main()
