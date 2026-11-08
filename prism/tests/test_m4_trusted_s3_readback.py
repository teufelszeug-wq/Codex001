import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from io import BytesIO
from prism_ops.trusted_s3_readback import verified_s3_readback

class TrustedReadbackTests(unittest.TestCase):
    def setUp(self):
        self.raw = b"canonical-forecast"
        self.until = datetime.now(timezone.utc) + timedelta(days=30)
        self.s3 = Mock()
        self.s3.get_object_retention.return_value = {
            "Retention": {"Mode": "COMPLIANCE", "RetainUntilDate": self.until}}
        self.s3.get_object.return_value = {
            "VersionId": "v1", "Body": BytesIO(self.raw)}
        self.kw = dict(bucket="bucket", key="forecast.json", version_id="v1",
                       expected_sha256=hashlib.sha256(self.raw).hexdigest(),
                       min_retention_until=self.until-timedelta(days=1))

    def test_success_mock(self):
        result = verified_s3_readback(self.s3, **self.kw)
        self.assertTrue(result["retention_verified"])
        self.assertEqual(result["readback_bytes"], self.raw)
        self.assertEqual(self.s3.get_object.call_args.kwargs["VersionId"], "v1")

    def test_governance_rejected(self):
        self.s3.get_object_retention.return_value["Retention"]["Mode"] = "GOVERNANCE"
        with self.assertRaisesRegex(ValueError, "WORM_RETENTION_UNVERIFIED"):
            verified_s3_readback(self.s3, **self.kw)

    def test_wrong_version_rejected(self):
        self.s3.get_object.return_value["VersionId"] = "v2"
        with self.assertRaisesRegex(ValueError, "VERSION_READBACK_MISMATCH"):
            verified_s3_readback(self.s3, **self.kw)

    def test_tampered_bytes_rejected(self):
        self.s3.get_object.return_value["Body"] = BytesIO(b"tampered")
        with self.assertRaisesRegex(ValueError, "PERSISTENCE_READBACK_FAILED"):
            verified_s3_readback(self.s3, **self.kw)

    def test_oversized_readback_rejected_before_hash(self):
        self.s3.get_object.return_value["Body"] = BytesIO(b"x" * 32)
        with self.assertRaisesRegex(ValueError, "READBACK_SIZE_LIMIT_EXCEEDED"):
            verified_s3_readback(self.s3, **dict(self.kw, max_bytes=16))

    def test_invalid_size_limit_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_READBACK_SIZE_LIMIT"):
            verified_s3_readback(self.s3, **dict(self.kw, max_bytes=True))

    def test_short_retention_rejected(self):
        self.s3.get_object_retention.return_value["Retention"]["RetainUntilDate"] = self.until-timedelta(days=2)
        with self.assertRaisesRegex(ValueError, "WORM_RETENTION_UNVERIFIED"):
            verified_s3_readback(self.s3, **self.kw)

    def test_null_version_rejected(self):
        with self.assertRaisesRegex(ValueError, "VERSION_ID_MISSING"):
            verified_s3_readback(self.s3, **dict(self.kw, version_id="null"))
if __name__ == "__main__":
    unittest.main()
