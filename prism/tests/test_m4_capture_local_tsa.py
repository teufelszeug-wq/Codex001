"""Capture/independent reverify orchestration with real LOCAL TSA and fake S3.

Nothing in this suite is a production provider, official data, or live race.
"""
from io import BytesIO
from unittest.mock import patch
import unittest

from prism_ops.m4_capture import (
    capture_pre_candidate, verify_candidate_independently)


class Backend:
    def __init__(self):
        self.objects = {}
        self.counter = 0
        self.put_count = 0
        self.retention_mode = "COMPLIANCE"


class FakeClient:
    def __init__(self, backend):
        self.backend = backend

    def put_object(self, **kwargs):
        b = self.backend
        b.counter += 1
        b.put_count += 1
        ver = f"v{b.counter}"
        b.objects[(kwargs["Key"], ver)] = {
            "data": kwargs["Body"],
            "until": kwargs["ObjectLockRetainUntilDate"],
        }
        return {"VersionId": ver}

    def get_object_retention(self, **kwargs):
        obj = self.backend.objects[(kwargs["Key"], kwargs["VersionId"])]
        return {"Retention": {"Mode": self.backend.retention_mode,
                              "RetainUntilDate": obj["until"]}}

    def get_object(self, **kwargs):
        obj = self.backend.objects[(kwargs["Key"], kwargs["VersionId"])]
        return {"VersionId": kwargs["VersionId"], "Body": BytesIO(obj["data"])}


class CaptureWithLocalTSA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import inside setUpClass to avoid unittest rediscovering test class.
        from test_m4_local_tsa_mock_s3_e2e import FullContractWithLocalCrypto
        cls.fixture = FullContractWithLocalCrypto
        cls.fixture.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.tearDownClass()

    def setUp(self):
        self.backend = Backend()
        self.writer = FakeClient(self.backend)
        self.reader = FakeClient(self.backend)
        self.official = dict(self.fixture.context if hasattr(self.fixture, "context")
                             else {
                                 "official_race_id": self.fixture.forecast["race_id"],
                                 "official_scheduled_off": self.fixture.forecast["scheduled_off"],
                                 "official_entries": self.fixture.entries,
                                 "official_as_of": self.fixture.source.isoformat(),
                                 "official_result_exposed": False,
                                 "official_race_cancelled": False,
                             })

    def _timestamp_locally(self, url, der):
        self.assertEqual(url, "https://tsa.test.invalid/local-ephemeral")
        p = self.fixture.root
        p.joinpath("capture_req.tsq").write_bytes(der)
        self.fixture._run("openssl", "ts", "-reply", "-config", "tsa.cnf",
                          "-queryfile", "capture_req.tsq",
                          "-out", "capture_resp.tsr")
        return p.joinpath("capture_resp.tsr").read_bytes()

    def _capture(self, **kwargs):
        args = {
            "s3_writer": self.writer, "s3_reader": self.reader,
            "s3_bucket": "synthetic", "s3_prefix": "pre/",
            "tsa_url": "https://tsa.test.invalid/local-ephemeral",
            "tsa_ca_pem": self.fixture.ca, "tsa_crl_pem": self.fixture.crl,
            "tsa_policy_oid": "1.2.3.4.5",
            "clock": lambda: self.fixture.now,
        }
        args.update(kwargs)
        with patch("prism_ops.m4_capture.request_timestamp",
                   side_effect=self._timestamp_locally):
            return capture_pre_candidate(
                self.fixture.forecast, self.official, **args)

    def _independent(self, captured, **kwargs):
        args = {
            "s3_reader": self.reader, "s3_bucket": "synthetic",
            "s3_prefix": "pre/", "manifest_key": captured["manifest_key"],
            "manifest_version_id": captured["manifest_version_id"],
            "manifest_sha256": captured["manifest_sha256"],
            "official_context": self.official, "tsa_ca_pem": self.fixture.ca,
            "tsa_crl_pem": self.fixture.crl,
            "tsa_policy_oid": "1.2.3.4.5",
        }
        args.update(kwargs)
        return verify_candidate_independently(**args)

    def test_capture_and_reverify_in_distinct_clients(self):
        self.assertIsNot(self.writer, self.reader)
        captured = self._capture()
        self.assertEqual(
            captured["status"], "CAPTURED_PRE_CANDIDATE_NOT_INDEPENDENTLY_VERIFIED")
        self.assertEqual(self.backend.put_count, 2)
        verified = self._independent(captured)
        self.assertEqual(
            verified["status"], "CRYPTO_WORM_PRE_VERIFIED_OFFICIAL_SOURCE_STILL_REQUIRED")
        self.assertEqual(verified["race_id"], self.fixture.forecast["race_id"])

    def test_tampered_manifest_rejected(self):
        captured = self._capture()
        key = (captured["manifest_key"], captured["manifest_version_id"])
        self.backend.objects[key]["data"] = b"{}"
        with self.assertRaisesRegex(ValueError, "PERSISTENCE_READBACK_FAILED"):
            self._independent(captured)

    def test_governance_mode_rejected_by_independent_reader(self):
        captured = self._capture()
        self.backend.retention_mode = "GOVERNANCE"
        with self.assertRaisesRegex(ValueError, "WORM_RETENTION_UNVERIFIED"):
            self._independent(captured)

    def test_mismatched_tsa_trust_policy_rejected(self):
        captured = self._capture()
        with self.assertRaisesRegex(ValueError, "TSA_TRUST_POLICY_MISMATCH"):
            self._independent(captured, tsa_policy_oid="1.2.3.4.6")

    def test_late_or_unverified_official_data_cannot_start_upload(self):
        with self.assertRaisesRegex(ValueError, "NO_SAFE_PRE_WINDOW"):
            self._capture(clock=lambda: self.fixture.off)
        self.assertEqual(self.backend.put_count, 0)
        self.official["official_result_exposed"] = None
        with self.assertRaisesRegex(ValueError, "OFFICIAL_RACE_NOT_PRE"):
            self._capture()
        self.assertEqual(self.backend.put_count, 0)


if __name__ == "__main__":
    unittest.main()
