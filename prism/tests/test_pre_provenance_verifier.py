"""Fail-closed regression tests for M4 provenance verifier (stdlib unittest)."""
import json
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from prism_ops.pre_provenance_verifier import verify_rfc3161_receipt, verify_git_commit_readback

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


    def test_git_commit_readback_accepts_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", tmp, "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", tmp, "config", "user.name", "PRISM test"], check=True)
            (repo / "forecast.json").write_bytes(self.raw)
            subprocess.run(["git", "-C", tmp, "add", "forecast.json"], check=True)
            subprocess.run(["git", "-C", tmp, "commit", "-qm", "pre forecast"], check=True)
            commit = subprocess.check_output(["git", "-C", tmp, "rev-parse", "HEAD"], text=True).strip()
            location = f"git-commit:{commit}:forecast.json"
            self.assertTrue(verify_git_commit_readback(self.raw, location, tmp))
            (repo / "forecast.json").write_bytes(b"mutable worktree replacement")
            self.assertTrue(verify_git_commit_readback(self.raw, location, tmp))
            with self.assertRaisesRegex(ValueError, "PERSISTENCE_READBACK_FAILED"):
                verify_git_commit_readback(b"wrong", location, tmp)
            with self.assertRaisesRegex(ValueError, "GIT_OBJECT_READBACK_FAILED"):
                verify_git_commit_readback(self.raw, f"git-commit:{commit}:missing.json", tmp)

    def test_fake_commit_and_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "GIT_COMMIT_NOT_FOUND"):
                verify_git_commit_readback(self.raw, "git-commit:" + "0" * 40 + ":forecast.json", tmp)
            for location in ("git-commit:abc123", "s3-version:unverified",
                             "git-commit:" + "0" * 40 + ":../forecast.json",
                             "git-commit:" + "0" * 40 + ":forecast\\\\evil.json"):
                with self.subTest(location=location):
                    with self.assertRaisesRegex(ValueError, "IMMUTABLE_LOCATION_UNVERIFIED"):
                        verify_git_commit_readback(self.raw, location, tmp)

    def test_receipt_rejects_unverified_storage_before_openssl(self):
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_LOCATION_UNVERIFIED"):
            verify_rfc3161_receipt(self.raw, self.raw, b"token", b"CA",
                                   "git-commit:" + "a" * 40 + ":forecast.json",
                                   request_der=b"tsq")

if __name__ == "__main__":
    unittest.main()
