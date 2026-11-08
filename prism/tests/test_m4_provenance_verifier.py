"""M4 fail-closed unit tests. Run with PYTHONPATH=prism/src python -m unittest discover -s prism/tests."""
import json
import unittest
from unittest.mock import patch
from prism_ops.pre_provenance_verifier import verify_rfc3161_receipt

FORECAST = {"race_id": "TEST-RACE", "scheduled_off": "2026-11-09T10:00:00+09:00",
            "source_as_of": "2026-11-09T09:00:00+09:00", "saved_at": "2026-11-09T09:01:00+09:00"}
RAW = json.dumps(FORECAST, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

class M4ReceiptTests(unittest.TestCase):
    def call(self, **kw):
        args = dict(forecast_bytes=RAW, readback_bytes=RAW,
                    tsa_response_der=b"not-a-real-token", trusted_tsa_ca_pem=b"not-a-real-ca",
                    immutable_location="git-commit:test", request_der=b"tsq")
        args.update(kw)
        return verify_rfc3161_receipt(**args)

    def test_reject_readback_mutation(self):
        with self.assertRaisesRegex(ValueError, "PERSISTENCE_READBACK_FAILED"):
            self.call(readback_bytes=RAW + b"x")

    def test_reject_missing_tsa(self):
        with self.assertRaisesRegex(ValueError, "RFC3161_TOKEN_MISSING"):
            self.call(tsa_response_der=b"")

    def test_reject_unpinned_storage(self):
        with self.assertRaisesRegex(ValueError, "IMMUTABLE_LOCATION_UNVERIFIED"):
            self.call(immutable_location="https://example.org/editable")

    def test_reject_noncanonical_json(self):
        with self.assertRaisesRegex(ValueError, "NONCANONICAL_FORECAST_BYTES"):
            self.call(forecast_bytes=b'{"race_id":"TEST-RACE", "scheduled_off":"2026-11-09T10:00:00+09:00","source_as_of":"2026-11-09T09:00:00+09:00"}',
                      readback_bytes=b'{"race_id":"TEST-RACE", "scheduled_off":"2026-11-09T10:00:00+09:00","source_as_of":"2026-11-09T09:00:00+09:00"}')

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_reject_invalid_signature(self, run):
        import hashlib
        imprint = hashlib.sha256(RAW).digest()
        rows = ["%04x - %s  %s" % (i, " ".join("%02x" % b for b in imprint[i:i+16]), "."*16) for i in (0,16)]
        query = "Hash Algorithm: sha256\nMessage data:\n" + "\n".join(rows) + "\n"
        run.side_effect = [type("R", (), {"returncode":0,"stdout":query})(),
                           type("R", (), {"returncode":1,"stdout":""})()]
        with self.assertRaisesRegex(ValueError, "RFC3161_SIGNATURE_OR_IMPRINT_INVALID"):
            self.call()

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_accept_only_mocked_valid_rfc3161_before_off(self, run):
        # Unit test only: mocks do not prove real cryptographic verification.
        import hashlib
        imprint = hashlib.sha256(RAW).digest()
        rows = ["%04x - %s  %s" % (i, " ".join("%02x" % b for b in imprint[i:i+16]), "."*16) for i in (0,16)]
        query = "Hash Algorithm: sha256\nMessage data:\n" + "\n".join(rows) + "\n"
        run.side_effect = [type("R", (), {"returncode": 0, "stdout": query})(),
                           type("R", (), {"returncode": 0, "stdout": ""})(),
                           type("R", (), {"returncode": 0,
                               "stdout": "Time stamp: Nov 9 00:30:00 2026 GMT\n"})()]
        receipt = self.call()
        self.assertEqual(receipt["race_id"], "TEST-RACE")
        self.assertEqual(receipt["proof_kind"], "RFC3161_OPENSSL_VERIFIED")

    @patch("prism_ops.pre_provenance_verifier.subprocess.run")
    def test_reject_mocked_timestamp_after_off(self, run):
        import hashlib
        imprint = hashlib.sha256(RAW).digest()
        rows = ["%04x - %s  %s" % (i, " ".join("%02x" % b for b in imprint[i:i+16]), "."*16) for i in (0,16)]
        query = "Hash Algorithm: sha256\nMessage data:\n" + "\n".join(rows) + "\n"
        run.side_effect = [type("R", (), {"returncode": 0, "stdout": query})(),
                           type("R", (), {"returncode": 0, "stdout": ""})(),
                           type("R", (), {"returncode": 0,
                               "stdout": "Time stamp: Nov 9 01:00:00 2026 GMT\\n"})()]
        with self.assertRaisesRegex(ValueError, "RFC3161_TIMESTAMP_AFTER_OFF"):
            self.call()

if __name__ == "__main__":
    unittest.main()
