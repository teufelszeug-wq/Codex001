import unittest
from video_forecast_bridge import attach_video_evidence

BASE={"race_id":"20261123-JRA-TOKYO-11","runners":[{"horse_name":"TEST HORSE"}]}
E={"evidence_id":"ev1","race_id":BASE["race_id"],"horse_name":"TEST HORSE","target_date":"2026-11-23","publisher":"publisher","url":"https://example.org/video","published_at":None,"checked_at":"2026-11-22T10:00:00+09:00","check_method":"playback","checked_by":"reviewer","video_start":10,"video_end":20,"status":"partial_playback","observations":"stride","article_claims":"","interpretation":"none","changed_forecast":False}
S="2026-11-22T12:00:00+09:00"
O="2026-11-23T15:30:00+09:00"
class TestBridge(unittest.TestCase):
 def run_bridge(self, items, phase="pre_race"):
  return attach_video_evidence(BASE,items,saved_at=S,off_at=O,phase=phase)
 def test_verified(self):
  self.assertEqual(len(self.run_bridge([E])["video_evidence"]),1)
 def test_page_only(self):
  e=dict(E,status="page_only",video_start=None,video_end=None)
  self.assertEqual(self.run_bridge([e])["video_evidence_withheld"][0]["reason"],"no_verified_playback")
 def test_future(self):
  e=dict(E,checked_at="2026-11-23T10:00:00+09:00")
  self.assertEqual(self.run_bridge([e])["video_evidence_withheld"][0]["reason"],"post_snapshot_evidence")
 def test_wrong_horse(self):
  with self.assertRaises(ValueError): self.run_bridge([dict(E,horse_name="OTHER")])
 def test_duplicate(self):
  with self.assertRaises(ValueError): self.run_bridge([E,E])
 def test_no_mutation(self):
  self.run_bridge([E]);self.assertNotIn("video_evidence",BASE)
 def test_review(self):
  e=dict(E,checked_at="2026-11-24T10:00:00+09:00")
  self.assertEqual(len(self.run_bridge([e],phase="review")["video_evidence"]),1)
if __name__=="__main__":unittest.main()
