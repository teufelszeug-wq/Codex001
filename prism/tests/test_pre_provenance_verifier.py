"""Fail-closed regression tests for M4 provenance verifier (stdlib unittest)."""
import json
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from prism_ops.pre_provenance_verifier import verify_rfc3161_receipt

def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.forecast = {"race_id": "TEST-1", "scheduled_off": "2026-11-08T12:00:00+09:00",
                         "source_as_of": "2026-11-08T10:00:00+09:00"}
        self.raw = canonical(self.forecast)
        self.args = (self.raw, self.raw, b"token", b"trusted CA", "git-commit:abc123")

    def test_readback_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "PERSISTENCE_READBACK_FAILED"):
            verify_rfc3161_receipt(self.raw, self.raw+b"x", b"token", b"CA", "git-commit:abc")

    def test_missing_token_rejected(self):
        with self.assertRaisesRegex(ValueError, "RFC3161_TOKEN_MISSING"):
            verify_rfc3161_receipt(self.raw, self.raw, b"", b"CA", "git-commit:abc")

    def test_unpinned_location_rejected(self):
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_LOCATION_UNVERIFIED"):
            verify_rfc3161_receipt(self.raw, self.raw, b"token", b"CA", "mutable:abc")

    def test_noncanonical_bytes_rejected(self):
        raw = json.dumps(self.forecast, indent=2).encode()
        with self.assertRaisesRegex(ValueError, "NONCANONICAL_FORECAST_BYTES"):
            verify_rfc3161_receipt(raw, raw, b"token", b"CA", "git-commit:abc")

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_bad_signature_rejected(self, run):
        run.return_value.returncode = 1
        with self.assertRaisesRegex(ValueError, "RFC3161_SIGNATURE_OR_IMPRINT_INVALID"):
            verify_rfc3161_receipt(*self.args)

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_timestamp_after_off_rejected(self, run):
        run.side_effect = [
            type("Result", (), {"returncode": 0, "stdout": ""})(),
            type("Result", (), {"returncode": 0, "stdout": "Time stamp: Nov  8 03:01:00 2026 GMT\n"})(),
        ]
        with self.assertRaisesRegex(ValueError, "RFC3161_TIMESTAMP_AFTER_OFF"):
            verify_rfc3161_receipt(*self.args)

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_timestamp_before_source_rejected(self, run):
        run.side_effect = [
            type("Result", (), {"returncode": 0, "stdout": ""})(),
            type("Result", (), {"returncode": 0, "stdout": "Time stamp: Nov  8 00:59:00 2026 GMT\n"})(),
        ]
        with self.assertRaisesRegex(ValueError, "RFC3161_TIMESTAMP_BEFORE_SOURCE"):
            verify_rfc3161_receipt(*self.args)

if __name__ == "__main__":
    unittest.main()
