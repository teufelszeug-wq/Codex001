import unittest
from video_evidence_gate import validate

def sample():
    return dict(evidence_id="ev1",race_id="20261123-JRA-TOKYO-11",
      horse_name="TEST HORSE",target_date="2026-11-23",publisher="Example",
      url="https://example.com/video",published_at=None,
      checked_at="2026-11-22T12:00:00+09:00",check_method="page check",
      checked_by="reviewer",video_start=None,video_end=None,status="page_only",
      observations="",article_claims="",interpretation="",changed_forecast=False)

class VideoGateTests(unittest.TestCase):
    def gate(self,x,**kw):
        return validate(x,forecast_saved_at="2026-11-22T20:00:00+09:00",
          off_at="2026-11-23T15:30:00+09:00",**kw)
    def test_page_only(self): self.assertTrue(self.gate(sample()))
    def test_future_check(self):
        x=sample();x["checked_at"]="2026-11-23T12:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"future"):self.gate(x)
    def test_future_publish(self):
        x=sample();x["published_at"]="2026-11-23T10:00:00+09:00";x["checked_at"]="2026-11-23T11:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"future"):self.gate(x)
    def test_unplayed_range(self):
        x=sample();x["video_start"]=10;x["video_end"]=20
        with self.assertRaisesRegex(ValueError,"unplayed"):self.gate(x)
    def test_played(self):
        x=sample();x.update(status="partial_playback",video_start=10,video_end=20,check_method="playback")
        self.assertTrue(self.gate(x))
    def test_unverified_cannot_change(self):
        x=sample();x["changed_forecast"]=True
        with self.assertRaisesRegex(ValueError,"unverified"):self.gate(x)
    def test_review_accepts_late_check(self):
        x=sample();x["checked_at"]="2026-11-24T12:00:00+09:00"
        self.assertTrue(validate(x,phase="review"))
    def test_naive_timestamp(self):
        x=sample();x["checked_at"]="2026-11-22T12:00:00"
        with self.assertRaisesRegex(ValueError,"timezone"):self.gate(x)
if __name__=="__main__":unittest.main()
