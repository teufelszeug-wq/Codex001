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
                         "source_as_of": "2026-11-08T10:00:00+09:00",
                         "saved_at": "2026-11-08T10:30:00+09:00"}
        self.raw = canonical(self.forecast)
        self.args = (self.raw, self.raw, b"token", b"trusted CA", "git-commit:abc123")

    def test_readback_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "PERSISTENCE_READBACK_FAILED"):
            verify_rfc3161_receipt(self.raw, self.raw+b"x", b"token", b"CA", "git-commit:abc")

    def test_missing_token_rejected(self):
        with self.assertRaisesRegex(ValueError, "RFC3161_TOKEN_MISSING"):
            verify_rfc3161_receipt(self.raw, self.raw, b"", b"CA", "git-commit:abc", request_der=b"tsq")

    def test_unpinned_location_rejected(self):
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_LOCATION_UNVERIFIED"):
            verify_rfc3161_receipt(self.raw, self.raw, b"token", b"CA", "mutable:abc", request_der=b"tsq")

    def test_noncanonical_bytes_rejected(self):
        raw = json.dumps(self.forecast, indent=2).encode()
        with self.assertRaisesRegex(ValueError, "NONCANONICAL_FORECAST_BYTES"):
            verify_rfc3161_receipt(raw, raw, b"token", b"CA", "git-commit:abc", request_der=b"tsq")

    def test_original_request_is_mandatory(self):
        with self.assertRaisesRegex(ValueError, "RFC3161_ORIGINAL_REQUEST_REQUIRED"):
            verify_rfc3161_receipt(*self.args)

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_request_unreadable_is_rejected(self, run):
        run.return_value.returncode = 1
        with self.assertRaisesRegex(ValueError, "RFC3161_REQUEST_UNREADABLE"):
            verify_rfc3161_receipt(*self.args, request_der=b"tsq")

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_wrong_request_imprint_is_rejected(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = ("Hash Algorithm: sha256\nMessage data:\n"
                                   "0000 - " + "00 " * 16 + "  ................\n"
                                   "0010 - " + "00 " * 16 + "  ................\n")
        with self.assertRaisesRegex(ValueError, "RFC3161_REQUEST_IMPRINT_MISMATCH"):
            verify_rfc3161_receipt(*self.args, request_der=b"tsq")

if __name__ == "__main__":
    unittest.main()
