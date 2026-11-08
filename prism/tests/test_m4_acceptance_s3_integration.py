"""M4 acceptance must not trust caller-provided readback or location."""
import hashlib
import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from prism_ops.forecast_completion_gate import validate_forecast

class S3:
    def __init__(self, raw, version="v1", mode="COMPLIANCE"):
        self.raw, self.version, self.mode = raw, version, mode
    def get_object_retention(self, **kwargs):
        return {"Retention": {"Mode": self.mode,
                "RetainUntilDate": datetime(2026, 12, 1, tzinfo=timezone.utc)}}
    def get_object(self, **kwargs):
        from io import BytesIO
        return {"VersionId": self.version, "Body": BytesIO(self.raw)}

class Integration(unittest.TestCase):
    def setUp(self):
        self.forecast = {"race_id": "TEST", "saved_at": "2026-11-08T10:01:00+09:00",
                         "scheduled_off": "2026-11-08T12:00:00+09:00",
                         "source_as_of": "2026-11-08T10:00:00+09:00",
                         "forecast_version": "v1", "input_snapshot": {},
                         "results_exposed": False, "entries": [{"horse_no":1,"horse_name":"A"}],
                         "agents": [], "required_agent_ids": []}
        from prism_ops.forecast_completion_gate import digest
        self.forecast["input_hash"] = digest({})
        self.raw = json.dumps(self.forecast, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode()
        self.context = {"s3_client": S3(self.raw), "bucket": "b", "key_prefix": "pre/", "tsa_ca_pem": b"CA", "official_race_id": "TEST", "official_scheduled_off": "2026-11-08T12:00:00+09:00", "official_entries": [{"horse_no": 1, "horse_name": "A"}], "official_as_of": "2026-11-08T10:00:00+09:00", "official_result_exposed": False, "official_race_cancelled": False}
        self.bundle = {"forecast_bytes":self.raw, 
                       "key":"pre/k", "version_id":"v1",
                       "tsa_response_der":b"tsr", "tsa_request_der":b"tsq", }

    @patch("prism_ops.pre_provenance_verifier.verify_rfc3161_receipt")
    def test_provider_readback_reaches_verifier(self, verify):
        verify.return_value = {"verified_by":"PRISM_TRUSTED_PERSISTENCE_VERIFIER"}
        validate_forecast(self.forecast, verify.return_value, self.bundle, verifier_context=self.context)
        self.assertEqual(verify.call_args.args[1], self.raw)
        self.assertEqual(verify.call_args.args[4], "s3-version:b/pre/k?versionId=v1")

    @patch("prism_ops.pre_provenance_verifier.verify_rfc3161_receipt")
    def test_mutated_s3_object_blocks_before_crypto(self, verify):
        self.context["s3_client"] = S3(self.raw + b"tamper")
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("PERSISTENCE_READBACK_FAILED" in e for e in errors))
        verify.assert_not_called()

    @patch("prism_ops.pre_provenance_verifier.verify_rfc3161_receipt")
    def test_governance_mode_blocks_before_crypto(self, verify):
        self.context["s3_client"] = S3(self.raw, mode="GOVERNANCE")
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("WORM_RETENTION_UNVERIFIED" in e for e in errors))
        verify.assert_not_called()

    @patch("prism_ops.pre_provenance_verifier.verify_rfc3161_receipt")
    def test_forged_caller_location_rejected(self, verify):
        verify.return_value = {"verified_by":"PRISM_TRUSTED_PERSISTENCE_VERIFIER"}
        self.bundle["immutable_location"] = "s3-version:attacker/fake?versionId=v1"
        errors = validate_forecast(self.forecast, verify.return_value, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("IMMUTABLE_LOCATION_MISMATCH" in e for e in errors))

    def test_producer_supplied_s3_client_rejected(self):
        self.bundle["trusted_s3_client"] = S3(self.raw)
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("UNTRUSTED_VERIFIER_CONFIG_IN_PROOF" in e for e in errors))

    def test_missing_verifier_context_rejected(self):
        errors = validate_forecast(self.forecast, None, self.bundle)["errors"]
        self.assertTrue(any("TRUSTED_VERIFIER_CONTEXT_REQUIRED" in e for e in errors))

    def test_forged_official_off_rejected(self):
        self.context["official_scheduled_off"] = "2026-11-08T11:00:00+09:00"
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("OFFICIAL_SCHEDULED_OFF_MISMATCH" in e for e in errors))

    def test_forged_race_identity_rejected(self):
        self.context["official_race_id"] = "OTHER"
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("OFFICIAL_RACE_ID_MISMATCH" in e for e in errors))

    def test_forged_runner_name_rejected(self):
        self.context["official_entries"] = [{"horse_no": 1, "horse_name": "B"}]
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("OFFICIAL_ENTRIES_MISMATCH" in e for e in errors))

    def test_official_entries_unavailable_rejected(self):
        self.context["official_entries"] = []
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("OFFICIAL_ENTRIES_UNAVAILABLE" in e for e in errors))

    def test_stale_official_feed_rejected(self):
        self.context["official_as_of"] = "2026-11-08T09:00:00+09:00"
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("OFFICIAL_FEED_STALE" in e for e in errors))

    def test_results_exposed_rejected(self):
        self.context["official_result_exposed"] = True
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("OFFICIAL_RESULT_EXPOSURE_UNVERIFIED" in e for e in errors))

    def test_cancelled_race_rejected(self):
        self.context["official_race_cancelled"] = True
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("OFFICIAL_RACE_STATUS_UNVERIFIED" in e for e in errors))

    def test_missing_official_feed_time_rejected(self):
        del self.context["official_as_of"]
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("OFFICIAL_FEED_TIME_UNVERIFIED" in e for e in errors))

    def test_key_outside_pinned_prefix_rejected(self):
        self.bundle["key"] = "outside/k"
        errors = validate_forecast(self.forecast, None, self.bundle, verifier_context=self.context)["errors"]
        self.assertTrue(any("UNTRUSTED_OBJECT_KEY" in e for e in errors))

if __name__ == "__main__":
    unittest.main()
