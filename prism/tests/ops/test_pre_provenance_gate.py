"""Regression tests for fail-closed PRE provenance validation."""
import unittest
from prism_ops.forecast_completion_gate import validate_forecast, digest


def sample():
    snapshot = {"race_id": "test-race", "case": "synthetic"}
    return {
        "race_id": "test-race", "input_snapshot": snapshot, "input_hash": digest(snapshot), "forecast_version": "v1",
        "source_as_of": "2026-11-07T12:00:00+09:00",
        "saved_at": "2026-11-07T12:30:00+09:00",
        "scheduled_off": "2026-11-07T14:00:00+09:00",
        "immutable_ref": "example:immutable-record",
        "external_timestamp_proof": "example:trusted-timestamp",
        "results_exposed": False,
        "entries": [{"horse_no": 1, "horse_name": "A"}, {"horse_no": 2, "horse_name": "B"}],
        "required_agent_ids": ["RIO"],
        "agents": [{"agent_id": "RIO", "picks": [{"mark": "◎", "horse_no": 1, "horse_name": "A"}], "pass_reason": "insufficient edge"}],
        "editorial": {"picks": [{"mark": "◎", "horse_no": 1, "horse_name": "A"}], "pass_reason": "insufficient edge"},
        "evidence": [{"source": "example:official-card", "kind": "entries", "available_at": "2026-11-07T12:00:00+09:00"}],
    }


class TestPreProvenanceGate(unittest.TestCase):
    def test_complete_shape_cannot_bypass_external_proof(self):
        result = validate_forecast(sample())
        self.assertFalse(result["complete"])
        self.assertIn("CRYPTOGRAPHIC_PROOF_BUNDLE_MISSING", result["errors"])
        self.assertNotIn("INVALID_INPUT_SNAPSHOT", result["errors"])
        self.assertNotIn("RIO:INVALID_PICKS", result["errors"])

    def test_missing_external_proof_fails_closed(self):
        f = sample()
        del f["external_timestamp_proof"]
        self.assertIn("CRYPTOGRAPHIC_PROOF_BUNDLE_MISSING", validate_forecast(f)["errors"])

    def test_post_result_exposure_fails_closed(self):
        f = sample()
        f["results_exposed"] = True
        self.assertIn("RESULT_EXPOSURE_NOT_EXCLUDED", validate_forecast(f)["errors"])

    def test_mismatched_horse_name_fails_closed(self):
        f = sample()
        f["agents"][0]["picks"][0]["horse_name"] = "WRONG"
        self.assertIn("RIO:INVALID_PICKS", validate_forecast(f)["errors"])

    def test_missing_input_identity_fails_closed(self):
        f = sample()
        del f["input_hash"]
        self.assertIn("MISSING_FORECAST_IDENTITY", validate_forecast(f)["errors"])


if __name__ == "__main__":
    unittest.main()
