import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from datetime import datetime, timedelta, timezone
from prism_pre_day_gate import check_publication, append_revision

class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.race = {"race_id":"test-race","start_at":"2026-11-15T15:40:00+09:00","runners":[{"name":"架空馬A"}]}
        self.final = {"editorial":{"mode":"editorial","saved_at":"2026-11-14T18:00:00+09:00","picks":["架空馬A"]}}
    def test_valid_pre_day(self):
        self.assertTrue(check_publication(self.race,{"editorial":{}},[1,2,3,4,5],self.final,"2026-11-14T20:00:00+09:00")["ready"])
    def test_late_paper_fails(self):
        errors = check_publication(self.race, {"editorial": {}}, [1, 2, 3, 4, 5], self.final,
                                   "2026-11-15T08:00:00+09:00")["errors"]
        self.assertIn("LATE_PUBLICATION", [error.split(":", 1)[0] for error in errors])
    def test_unverified_independent_fails(self):
        self.final["editorial"]["mode"]="independent_execution"
        self.assertFalse(check_publication(self.race,{"editorial":{}},[1,2,3,4,5],self.final,"2026-11-14T20:00:00+09:00")["ready"])
    def test_missing_discussion_fails(self):
        self.assertFalse(check_publication(self.race,{"editorial":{}},[],self.final,"2026-11-14T20:00:00+09:00")["ready"])
    def test_revision_retains_original(self):
        old={"version":"v1","saved_at":"2026-11-14T18:00:00+09:00"}
        new={"version":"v2","saved_at":"2026-11-15T08:00:00+09:00"}
        self.assertEqual(append_revision([old],new),[old,new])

if __name__ == "__main__":
    unittest.main()
