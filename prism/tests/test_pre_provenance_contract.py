"""Regression tests for PRE fail-closed validation. Run: PYTHONPATH=prism/src python -m unittest discover -s prism/tests -p 'test_pre_provenance_contract.py'"""
import unittest
from prism_ops.forecast_completion_gate import validate_forecast, digest

def sample():
    entries = [{"horse_no": 3, "horse_name": "イリスロッソ"}, {"horse_no": 5, "horse_name": "ドナビッグベン"}]
    snapshot = {"race_id": "JRA-20261108-FUKUSHIMA-01", "entries": entries}
    agent = {"agent_id": "RIO", "picks": [{"mark": "◎", "horse_no": 3, "horse_name": "イリスロッソ"}],
             "tickets": [{"bet_type": "単勝", "selection": [3], "stake_yen": 100}]}
    return {"race_id": snapshot["race_id"], "scheduled_off": "2026-11-08T09:45:00+09:00",
            "saved_at": "2026-11-08T08:02:00+09:00", "source_as_of": "2026-11-08T08:00:00+09:00",
            "forecast_version": "TEST_ONLY", "input_snapshot": snapshot, "input_hash": digest(snapshot),
            "entries": entries, "agents": [agent], "required_agent_ids": ["RIO"],
            "editorial": {"picks": [{"mark": "◎", "horse_no": 5, "horse_name": "ドナビッグベン"}],
                          "tickets": [{"bet_type": "単勝", "selection": [5], "stake_yen": 100}]},
            "immutable_ref": "TEST_NOT_REAL", "external_timestamp_proof": "TEST_NOT_REAL",
            "persistence_readback_verified": True, "external_timestamp_verified": True,
            "results_exposed": False}

class PreProvenanceContract(unittest.TestCase):
    def test_forged_receipt_without_proof_fails(self):
        p = sample()
        fake = {"verified_by": "PRISM_TRUSTED_PERSISTENCE_VERIFIER",
                "race_id": p["race_id"], "forecast_sha256": digest(p),
                "trusted_saved_at": "2026-11-08T08:02:00+09:00",
                "immutable_location": "git-commit:fake",
                "readback_verified": True, "timestamp_verified": True}
        self.assertIn("CRYPTOGRAPHIC_PROOF_BUNDLE_MISSING",
                      validate_forecast(p, fake)["errors"])

    def test_missing_snapshot_fails(self):
        p = sample(); del p["input_snapshot"]
        self.assertIn("INPUT_SNAPSHOT_MISSING", validate_forecast(p)["errors"])
    def test_changed_snapshot_fails(self):
        p = sample(); p["input_snapshot"]["entries"][0]["horse_name"] = "ALTERED"
        self.assertIn("INPUT_HASH_MISMATCH", validate_forecast(p)["errors"])
    def test_unverified_external_timestamp_fails(self):
        p = sample(); p["external_timestamp_verified"] = False
        self.assertIn("PRE_PROVENANCE_NOT_INDEPENDENTLY_VERIFIED", validate_forecast(p)["errors"])
    def test_source_after_save_fails(self):
        p = sample(); p["source_as_of"] = "2026-11-08T08:03:00+09:00"
        self.assertIn("SOURCE_AFTER_SAVE", validate_forecast(p)["errors"])
    def test_result_exposure_unknown_fails(self):
        p = sample(); p["results_exposed"] = None
        self.assertIn("RESULT_EXPOSURE_NOT_EXCLUDED", validate_forecast(p)["errors"])
    def test_untrusted_boolean_flags_must_not_prove_external_timestamp(self):
        # Known security gap: arbitrary strings + caller-supplied booleans currently pass.
        p = sample()
        self.assertIn("PRE_PROVENANCE_NOT_INDEPENDENTLY_VERIFIED", validate_forecast(p)["errors"])

if __name__ == "__main__":
    unittest.main()
