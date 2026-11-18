import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import unittest
from prism_mdisc_sequence import audit, TOPICS
class Tests(unittest.TestCase):
    def setUp(self):
        self.race={"race_id":"synthetic","start_at":"2026-11-22T15:40:00+09:00","runners":[{"name":"架空馬"}]}
        self.pre={"rio":{"saved_at":"2026-11-20T12:00:00+09:00","mode":"editorial"}}
        self.ds=[{"topic":x,"saved_at":f"2026-11-20T13:{i:02d}:00+09:00","character_id":"rio","character_url":"https://example.invalid/rio","mode":"single_model_simulation"} for i,x in enumerate(TOPICS)]
        self.final={"rio":{"saved_at":"2026-11-20T14:00:00+09:00","mode":"editorial","picks":["架空馬"]}}
        self.paper={"published_at":"2026-11-21T09:00:00+09:00"}
    def check(self): return audit(self.race,self.pre,self.ds,self.final,self.paper)
    def test_valid(self): self.assertTrue(self.check()["ready"])
    def test_final_before_discussion(self):
        self.final["rio"]["saved_at"]="2026-11-20T12:30:00+09:00"
        self.assertIn("FINAL_BEFORE_DISCUSSION_END:rio",self.check()["errors"])
    def test_missing_topic(self):
        self.ds.pop()
        self.assertIn("TOPIC_MISSING:tickets",self.check()["errors"])
    def test_independent_unproven(self):
        self.final["rio"]["mode"]="independent_execution"
        self.assertIn("FINAL_EXECUTION_UNPROVEN:rio",self.check()["errors"])
    def test_pre_after_discussion(self):
        self.pre["rio"]["saved_at"]="2026-11-20T13:30:00+09:00"
        self.assertIn("PRE_NOT_BEFORE_DISCUSSION:rio",self.check()["errors"])
    def test_late_paper(self):
        self.paper["published_at"]="2026-11-22T08:00:00+09:00"
        self.assertIn("PAPER_NOT_PREVIOUS_DAY",self.check()["errors"])
    def test_pre_between_discussions(self):
        self.pre["rio"]["saved_at"]="2026-11-20T13:02:30+09:00"
        self.assertIn("PRE_NOT_BEFORE_DISCUSSION:rio",self.check()["errors"])
    def test_unknown_mode(self):
        self.final["rio"]["mode"]="pretend_independent"
        self.assertIn("FINAL_MODE_UNKNOWN:rio",self.check()["errors"])
    def test_final_without_pre(self):
        self.final["extra"]=dict(self.final["rio"])
        self.assertIn("FINAL_WITHOUT_PRE:extra",self.check()["errors"])
    def test_no_discussion_times(self):
        self.ds=[]
        self.assertIn("FINAL_BEFORE_DISCUSSION_END:rio",self.check()["errors"])
if __name__=="__main__": unittest.main()
