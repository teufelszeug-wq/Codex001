"""OpenSSL request parser regression: full 32-byte SHA256 and rejection cases."""
import hashlib
import json
import unittest
from unittest.mock import patch
from prism_ops.pre_provenance_verifier import verify_rfc3161_receipt

def output_for(raw, truncate=False):
    hexbytes = hashlib.sha256(raw).digest()
    if truncate:
        hexbytes = hexbytes[:16]
    rows = []
    for i in range(0, len(hexbytes), 16):
        part = hexbytes[i:i+16]
        rows.append("%04x - %s  %s" % (i, " ".join("%02x" % b for b in part),
                                        "." * len(part)))
    return "Hash Algorithm: sha256\nMessage data:\n" + "\n".join(rows) + "\n"

class ParserTests(unittest.TestCase):
    def setUp(self):
        self.data = {"race_id":"TEST", "saved_at":"2026-11-08T10:30:00+09:00", "source_as_of":"2026-11-08T10:00:00+09:00",
                     "scheduled_off":"2026-11-08T12:00:00+09:00"}
        self.raw = json.dumps(self.data, sort_keys=True, ensure_ascii=False,
                              separators=(",", ":")).encode()

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_full_sha256_reaches_signature_verification(self, run):
        run.side_effect = [
            type("R", (), {"returncode":0,"stdout":output_for(self.raw)})(),
            type("R", (), {"returncode":1,"stdout":""})(),
        ]
        with self.assertRaisesRegex(ValueError, "RFC3161_SIGNATURE_OR_IMPRINT_INVALID"):
            verify_rfc3161_receipt(self.raw, self.raw, b"response", b"ca",
                                   "s3-version:bucket/key?versionId=v1",
                                   request_der=b"request")
        self.assertEqual(run.call_count, 2)
        self.assertIn("-queryfile", run.call_args.args[0])

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_truncated_sha256_rejected_before_signature(self, run):
        run.return_value = type("R", (), {"returncode":0,
                                           "stdout":output_for(self.raw, truncate=True)})()
        with self.assertRaisesRegex(ValueError, "RFC3161_REQUEST_IMPRINT_MISMATCH"):
            verify_rfc3161_receipt(self.raw, self.raw, b"response", b"ca",
                                   "s3-version:bucket/key?versionId=v1",
                                   request_der=b"request")
        self.assertEqual(run.call_count, 1)

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_timestamp_before_forecast_save_rejected(self, run):
        run.side_effect = [
            type("R", (), {"returncode":0,"stdout":output_for(self.raw)})(),
            type("R", (), {"returncode":0,"stdout":""})(),
            type("R", (), {"returncode":0,
                            "stdout":"Time stamp: Nov  8 01:15:00 2026 GMT\n"})(),
        ]
        with self.assertRaisesRegex(ValueError, "RFC3161_TIMESTAMP_BEFORE_FORECAST_SAVE"):
            verify_rfc3161_receipt(self.raw, self.raw, b"response", b"ca",
                                   "s3-version:bucket/key?versionId=v1",
                                   request_der=b"request")

if __name__ == "__main__":
    unittest.main()
