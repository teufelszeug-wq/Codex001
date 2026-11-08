import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))
from prism_ops.run_readiness import audit_run

class RunReadinessTests(unittest.TestCase):
    def test_no_data(self):
        r=audit_run([],"2026-11-06T23:59:00+09:00")
        self.assertIsNone(r["official_race_denominator"])
        self.assertEqual(r["verified_pre_count"],0)
        self.assertEqual(r["status"],"OFFICIAL_DATA_MISSING")
    def test_future_race_not_counted_as_locked(self):
        race={"race_id":"synthetic-1","input_sha256":"abc","scheduled_off":"2026-11-07T10:00:00+09:00","official_entries_verified":True,"result_exposed":False,"pre_locked":False}
        r=audit_run([race],"2026-11-06T23:59:00+09:00")
        self.assertEqual(r["eligible_races"],["synthetic-1"])
        self.assertEqual(r["verified_pre_count"],0)
    def test_unknown_result_exposure_is_not_eligible(self):
        race={"race_id":"synthetic-1","input_sha256":"abc",
              "scheduled_off":"2026-11-07T10:00:00+09:00",
              "official_entries_verified":True,"result_exposed":None,"pre_locked":False}
        out=audit_run([race],"2026-11-06T23:59:00+09:00")
        self.assertEqual(out["eligible_races"],[])
        self.assertEqual(out["blocked"][0]["reason"],"RESULT_EXPOSURE_NOT_EXCLUDED")

    def test_expired_race(self):
        race={"race_id":"synthetic-1","input_sha256":"abc","scheduled_off":"2026-11-06T10:00:00+09:00","official_entries_verified":True}
        r=audit_run([race],"2026-11-06T23:59:00+09:00")
        self.assertEqual(r["eligible_races"],[])
        self.assertEqual(r["blocked"][0]["reason"],"NO_PRE_WINDOW")
if __name__=="__main__": unittest.main()
