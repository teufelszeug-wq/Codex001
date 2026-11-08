"""Real OpenSSL RFC3161 crypto integration using an EPHEMERAL LOCAL test CA/TSA.

This test makes real signatures and verifies cryptographic rejection. It does NOT
contact an independent TSA or prove production RFC3161/WORM acceptance.
Private test keys exist only in a temporary directory and are never committed.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from prism_ops.pre_provenance_verifier import verify_rfc3161_receipt


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL required")
class LocalRFC3161CryptoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.root.joinpath("tsa.ext").write_text(
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature\n"
            "extendedKeyUsage=critical,timeStamping\n"
            "subjectKeyIdentifier=hash\n"
            "authorityKeyIdentifier=keyid,issuer\n",
            encoding="ascii")
        cls._run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                 "-keyout", "ca.key", "-out", "ca.pem", "-days", "2",
                 "-subj", "/CN=PRISM local-test root",
                 "-addext", "basicConstraints=critical,CA:TRUE",
                 "-addext", "keyUsage=critical,keyCertSign,cRLSign")
        cls._run("openssl", "req", "-newkey", "rsa:2048", "-nodes",
                 "-keyout", "tsa.key", "-out", "tsa.csr",
                 "-subj", "/CN=PRISM local-test TSA")
        cls._run("openssl", "x509", "-req", "-in", "tsa.csr",
                 "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
                 "-out", "tsa.pem", "-days", "2", "-sha256",
                 "-extfile", "tsa.ext")
        cls.root.joinpath("serial.txt").write_text("01\n", encoding="ascii")
        cls.root.joinpath("tsa.cnf").write_text(
            "[tsa]\ndefault_tsa=tsa_config\n[tsa_config]\n"
            "serial=serial.txt\nsigner_cert=tsa.pem\nsigner_key=tsa.key\n"
            "signer_digest=sha256\ndefault_policy=1.2.3.4.5\n"
            "digests=sha256\naccuracy=secs:1\nordering=yes\n"
            "tsa_name=yes\ness_cert_id_chain=no\n",
            encoding="ascii")
        now = datetime.now(timezone.utc)
        cls.forecast = {
            "race_id": "SIM-RFC3161-LOCAL-ONLY",
            "source_as_of": (now - timedelta(minutes=6)).isoformat(),
            "saved_at": (now - timedelta(minutes=5)).isoformat(),
            "scheduled_off": (now + timedelta(days=1)).isoformat(),
        }
        cls.raw = json.dumps(cls.forecast, ensure_ascii=False,
                             sort_keys=True, separators=(",", ":")).encode("utf-8")
        cls.root.joinpath("forecast.json").write_bytes(cls.raw)
        cls._run("openssl", "ts", "-query", "-data", "forecast.json",
                 "-sha256", "-cert", "-out", "request.tsq")
        cls._run("openssl", "ts", "-reply", "-config", "tsa.cnf",
                 "-queryfile", "request.tsq", "-out", "reply.tsr")
        cls.query = cls.root.joinpath("request.tsq").read_bytes()
        cls.reply = cls.root.joinpath("reply.tsr").read_bytes()
        cls.ca = cls.root.joinpath("ca.pem").read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    @classmethod
    def _run(cls, *args):
        cmd = subprocess.run(args, cwd=cls.root, text=True,
                             capture_output=True, timeout=30)
        if cmd.returncode != 0:
            raise AssertionError("OpenSSL local TSA command failed: "
                                 + repr(args) + " / " + cmd.stderr)
        return cmd

    def _verify(self, *, original=None, readback=None, reply=None,
                request=None, ca=None):
        raw = self.raw if original is None else original
        # Isolate genuine local RFC3161 signature tests from storage backend.
        with patch("prism_ops.pre_provenance_verifier.verify_git_commit_readback", return_value=True):
            return verify_rfc3161_receipt(
            raw, raw if readback is None else readback,
            self.reply if reply is None else reply,
            self.ca if ca is None else ca,
            "s3-version:synthetic/pre/forecast?versionId=test-only",
            request_der=self.query if request is None else request)

    def test_real_signature_and_original_nonce_request_accepts(self):
        result = self._verify()
        self.assertEqual(result["proof_kind"], "RFC3161_OPENSSL_VERIFIED")
        self.assertEqual(result["race_id"], "SIM-RFC3161-LOCAL-ONLY")
        self.assertTrue(result["timestamp_verified"])

    def test_original_forecast_tampering_rejected(self):
        altered = dict(self.forecast, race_id="SIM-TAMPERED")
        raw = json.dumps(altered, sort_keys=True,
                         separators=(",", ":")).encode()
        with self.assertRaisesRegex(ValueError, "RFC3161_REQUEST_IMPRINT_MISMATCH"):
            self._verify(original=raw)

    def test_response_signature_tampering_rejected(self):
        tampered = bytearray(self.reply)
        tampered[-1] ^= 1
        with self.assertRaises(ValueError):
            self._verify(reply=bytes(tampered))

    def test_nonce_replay_with_second_request_rejected(self):
        self._run("openssl", "ts", "-query", "-data", "forecast.json",
                  "-sha256", "-cert", "-out", "other.tsq")
        second_request = self.root.joinpath("other.tsq").read_bytes()
        self.assertNotEqual(second_request, self.query)
        with self.assertRaisesRegex(ValueError, "RFC3161_SIGNATURE_OR_IMPRINT_INVALID"):
            self._verify(request=second_request)

    def test_untrusted_ca_rejected(self):
        with self.assertRaisesRegex(ValueError, "RFC3161_SIGNATURE_OR_IMPRINT_INVALID"):
            self._verify(ca=b"not a certificate")


if __name__ == "__main__":
    unittest.main()
