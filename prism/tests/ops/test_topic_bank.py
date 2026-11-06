"""Synthetic Topic Bank and roundtable gate tests."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from prism_ops.topic_bank import create_topic, add_candidate, coverage_gate, REQUIRED

class TopicBankTests(unittest.TestCase):
    def test_create(self):
        self.assertTrue(create_topic("展開","逃げ争いで差し有利","R1","pace","単騎逃げ","先行馬一覧")["topic_id"].startswith("TOP-"))
    def test_duplicate(self):
        t=create_topic("展開","逃げ争いで差し有利","R1","pace","単騎逃げ","先行馬一覧")
        b=[]
        self.assertEqual(add_candidate(b,t)["status"],"candidate")
        self.assertEqual(add_candidate(b,t)["status"],"duplicate")
        self.assertEqual(len(b),1)
    def test_missing_theme(self):
        self.assertFalse(coverage_gate({"topics":[],"participants":[]})["complete"])
    def test_all_topics_and_tickets(self):
        r={"topics":[{"theme":x,"utterances":["議論"],"evidence_status":"verified"} for x in REQUIRED],
           "participants":[{"agent_id":"rio","marks":[{"horse_no":1,"mark":"◎"}],"tickets":[{"bet_type":"単勝","selection":[1],"stake_yen":100}]}]}
        self.assertTrue(coverage_gate(r)["complete"])
    def test_no_agent_ticket(self):
        r={"topics":[{"theme":x,"utterances":["議論"],"evidence_status":"missing_documented"} for x in REQUIRED],
           "participants":[{"agent_id":"rio","marks":[{"horse_no":1,"mark":"◎"}],"tickets":[]}]}
        self.assertFalse(coverage_gate(r)["complete"])
    def test_fake_evidence_label_rejected(self):
        r={"topics":[{"theme":x,"utterances":["議論"],"evidence_status":"unverified"} for x in REQUIRED],
           "participants":[{"agent_id":"rio","marks":[{"horse_no":1,"mark":"◎"}],"pass_reason":"見送り"}]}
        self.assertFalse(coverage_gate(r)["complete"])
    def test_missing_agent_id_rejected(self):
        r={"topics":[{"theme":x,"utterances":["議論"],"evidence_status":"verified"} for x in REQUIRED],
           "participants":[{"marks":[{"horse_no":1,"mark":"◎"}],"pass_reason":"見送り"}]}
        self.assertFalse(coverage_gate(r)["complete"])

if __name__=="__main__": unittest.main()
