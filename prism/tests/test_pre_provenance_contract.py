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

    def test_settlement_rejects_missing_m4_proof(self):
        from prism_ops.forecast_completion_gate import settle_forecast
        p = sample()
        with self.assertRaisesRegex(ValueError, "CRYPTOGRAPHIC_PROOF_BUNDLE_MISSING"):
            settle_forecast(p, {"race_id": p["race_id"],
                                "official_source": "OFFICIAL_TEST_ONLY",
                                "ticket_outcomes": {}})

    def test_forged_proof_bundle_rejected(self):
        p = sample()
        forged = {"forecast_bytes": b"{}", "readback_bytes": b"{}",
                  "tsa_response_der": b"fake", "trusted_tsa_ca_pem": b"fake",
                  "immutable_location": "git-commit:fake"}
        self.assertTrue(any(x.startswith("CRYPTOGRAPHIC_PROOF_INVALID")
                            for x in validate_forecast(p, proof_bundle=forged)["errors"]))

    def test_provenance_is_not_required_inside_signed_forecast(self):
        p = sample()
        p.pop("immutable_ref", None)
        p.pop("external_timestamp_proof", None)
        result = validate_forecast(p)
        self.assertNotIn("PRE_PROVENANCE_UNVERIFIED", result["errors"])
        self.assertIn("CRYPTOGRAPHIC_PROOF_BUNDLE_MISSING", result["errors"])

    def test_signed_bytes_must_match_validated_forecast(self):
        from unittest.mock import patch
        from datetime import datetime, timezone
        from io import BytesIO
        import json
        p = sample()
        other = dict(p, forecast_version="ANOTHER_VERSION")
        signed = json.dumps(other, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")).encode()
        class PinnedS3:
            def get_object_retention(self, **kwargs):
                return {"Retention": {"Mode": "COMPLIANCE",
                        "RetainUntilDate": datetime(2026, 12, 1, tzinfo=timezone.utc)}}
            def get_object(self, **kwargs):
                return {"VersionId": "v1", "Body": BytesIO(signed)}
        context = {"s3_client": PinnedS3(), "bucket": "test", "key_prefix": "pre/",
                   "tsa_ca_pem": b"ca", "tsa_policy_oid": "1.2.3.4.5", "official_race_id": p["race_id"],
                   "official_scheduled_off": p["scheduled_off"],
                   "official_entries": p["entries"], "official_as_of": p["source_as_of"],
                   "official_result_exposed": False, "official_race_cancelled": False}
        bundle = {"forecast_bytes": signed, "key": "pre/test",
                  "version_id": "v1", "tsa_response_der": b"token",
                  "tsa_request_der": b"request"}
        context = {"s3_client": object(), "bucket": "trusted",
                   "key_prefix": "pre/", "tsa_ca_pem": b"ca",
                   "tsa_policy_oid": "1.2.3.4.5",
                   "official_race_id": p["race_id"],
                   "official_scheduled_off": p["scheduled_off"],
                   "official_entries": p["entries"],
                   "official_as_of": p["source_as_of"],
                   "official_result_exposed": False,
                   "official_race_cancelled": False}
        receipt = {"verified_by": "PRISM_TRUSTED_PERSISTENCE_VERIFIER",
                   "race_id": p["race_id"], "forecast_sha256": digest(p),
                   "trusted_saved_at": "2026-11-08T08:02:00+09:00",
                   "immutable_location": "s3-version:trusted/pre/test?versionId=v1",
                   "readback_verified": True, "timestamp_verified": True}
        immutable = {"readback_bytes": signed,
                     "immutable_location": receipt["immutable_location"]}
        with patch("prism_ops.trusted_s3_readback.verified_s3_readback",
                   return_value=immutable), patch(
                   "prism_ops.pre_provenance_verifier.verify_rfc3161_receipt",
                   return_value=receipt):
            result = validate_forecast(p, receipt, bundle, verifier_context=context)
        self.assertIn("SIGNED_FORECAST_PAYLOAD_MISMATCH", result["errors"])

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
