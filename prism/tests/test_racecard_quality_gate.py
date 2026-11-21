import unittest
from copy import deepcopy
from racecard_quality_gate import validate_staged_card

BASE = {"race_id":"20261122_JRA_01_01","source_id":"https://www.jra.go.jp/","source_sha256":"a"*64,"source_retrieved_at":"2026-11-21T08:00:00+09:00","scheduled_start_at":"2026-11-22T10:00:00+09:00","source_authenticity_verified":False,"horses":[{"horse_id":"A","horse_name":"甲","horse_number":1},{"horse_id":"B","horse_name":"乙","horse_number":2}]}
class GateTest(unittest.TestCase):
    def test_unverified_blocked(self):
        with self.assertRaisesRegex(ValueError,"unverified"): validate_staged_card(BASE)
    def test_research_staging_allowed(self):
        self.assertFalse(validate_staged_card(BASE,require_verified=False)["forecast_eligible"])
    def test_verified_with_cutoff(self):
        c=deepcopy(BASE); c["source_authenticity_verified"]=True
        self.assertEqual(validate_staged_card(c,prediction_at="2026-11-21T09:00:00+09:00")["runner_count"],2)
    def test_leak_cutoff(self):
        c=deepcopy(BASE); c["source_authenticity_verified"]=True
        with self.assertRaisesRegex(ValueError,"temporal leakage"): validate_staged_card(c,prediction_at="2026-11-21T07:00:00+09:00")
    def test_duplicate_number(self):
        c=deepcopy(BASE); c["horses"][1]["horse_number"]=1
        with self.assertRaisesRegex(ValueError,"duplicate horse number"): validate_staged_card(c,require_verified=False)
    def test_partial_number(self):
        c=deepcopy(BASE); del c["horses"][1]["horse_number"]
        with self.assertRaisesRegex(ValueError,"partially populated"): validate_staged_card(c,require_verified=False)
    def test_after_start(self):
        c=deepcopy(BASE); c["source_retrieved_at"]=c["scheduled_start_at"]
        with self.assertRaisesRegex(ValueError,"post-start"): validate_staged_card(c,require_verified=False)
if __name__=="__main__": unittest.main()
