import unittest
from prism.scripts.audit_operations_completion import audit_operations
TARGETS={"targets":[{"race_id":"SYNTHETIC-01"}]}
class TestOperationalGate(unittest.TestCase):
    def test_roles_are_not_independent_runs(self):
        artifacts=[{"race_id":"SYNTHETIC-01","kind":"forecast","forecaster_id":"RIO",
                    "pre_off_verified":True,"saved_at":"2026-11-15T10:00:00+09:00",
                    "version":1,"evidence_url":"fixture://commit",
                    "execution_mode":"role_play"}]
        result=audit_operations(TARGETS,artifacts)
        self.assertFalse(result["races"][0]["rio_independent_verified"])
        self.assertEqual(result["complete_count"],0)
    def test_no_artifacts_is_critical(self):
        self.assertEqual(audit_operations(TARGETS,[])["status"],"CRITICAL")
    def test_full_evidence(self):
        base={"race_id":"SYNTHETIC-01","kind":"forecast","pre_off_verified":True,
              "saved_at":"2026-11-15T10:00:00+09:00","version":1,
              "evidence_url":"fixture://commit","execution_mode":"independent","run_id":"run"}
        artifacts=[dict(base,forecaster_id="DESK"),dict(base,forecaster_id="RIO"),
                   dict(base,forecaster_id="SPECIALIST"),
                   {"race_id":"SYNTHETIC-01","kind":"roundtable","topics":["a","b","c","d","e"],"evidence_url":"fixture://dialogue"},
                   {"race_id":"SYNTHETIC-01","kind":"paper","vertical_qa_pass":True,"evidence_url":"fixture://paper"},
                   {"race_id":"SYNTHETIC-01","kind":"settlement","official_result_url":"fixture://official",
                    "stake_unit_yen":100,"evidence_url":"fixture://settlement"}]
        self.assertEqual(audit_operations(TARGETS,artifacts)["complete_count"],1)
if __name__=="__main__":unittest.main()
