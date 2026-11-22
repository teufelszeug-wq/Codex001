"""M4 WORM storage contract tests, mocked S3 API only."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from prism_ops.worm_storage import store_and_verify

class WormStorageTests(unittest.TestCase):
    def client(self):
        s3 = Mock()
        s3.put_object.return_value = {"VersionId": "version-123"}
        s3.get_object_retention.return_value = {"Retention": {
            "Mode": "COMPLIANCE", "RetainUntilDate": datetime.now(timezone.utc) + timedelta(days=31)}}
        s3.get_object.return_value = {"VersionId": "version-123", "Body": Mock(read=lambda *args: b"forecast")}
        return s3

    def test_mocked_versioned_worm_readback(self):
        s3 = self.client()
        result = store_and_verify(s3, "bucket", "race.json", b"forecast")
        self.assertEqual(result["version_id"], "version-123")
        self.assertEqual(s3.get_object.call_args.kwargs["VersionId"], "version-123")

    def test_missing_version_fails(self):
        s3 = self.client()
        s3.put_object.return_value = {}
        with self.assertRaisesRegex(ValueError, "VERSION_ID_MISSING"):
            store_and_verify(s3, "bucket", "race.json", b"forecast")

    def test_wrong_version_readback_fails(self):
        s3 = self.client()
        s3.get_object.return_value["VersionId"] = "version-attacker"
        with self.assertRaisesRegex(ValueError, "VERSION_READBACK_MISMATCH"):
            store_and_verify(s3, "bucket", "race.json", b"forecast")

    def test_invalid_retention_parameter_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_WORM_CONFIG"):
            store_and_verify(self.client(), "bucket", "race.json",
                             b"forecast", retention_days=True)

    def test_governance_mode_fails(self):
        s3 = self.client()
        s3.get_object_retention.return_value["Retention"]["Mode"] = "GOVERNANCE"
        with self.assertRaisesRegex(ValueError, "WORM_RETENTION_NOT_VERIFIED"):
            store_and_verify(s3, "bucket", "race.json", b"forecast")

    def test_mutated_readback_fails(self):
        s3 = self.client()
        s3.get_object.return_value["Body"].read = lambda *args: b"altered"
        with self.assertRaisesRegex(ValueError, "PERSISTENCE_READBACK_FAILED"):
            store_and_verify(s3, "bucket", "race.json", b"forecast")

if __name__ == "__main__":
    unittest.main()
