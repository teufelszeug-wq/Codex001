"""Real local RFC3161 signature + simulated COMPLIANCE S3 + settlement E2E.

NO external TSA, no cloud provider and no official racing data are used.
This is a deterministic contract/integration test, never a live VERIFIED_PRE.
"""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

from prism_ops.forecast_completion_gate import digest, validate_forecast
from prism_ops.pre_provenance_verifier import verify_rfc3161_receipt
from prism_ops.verified_settlement import settle_verified_pre


class SimulatedS3:
    def __init__(self, raw, retention_until):
        self.raw = raw
        self.retention_until = retention_until

    def get_object_retention(self, **kwargs):
        return {"Retention": {"Mode": "COMPLIANCE",
                              "RetainUntilDate": self.retention_until}}

    def get_object(self, **kwargs):
        return {"VersionId": "v1", "Body": BytesIO(self.raw)}


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL required")
class FullContractWithLocalCrypto(unittest.TestCase):
    @classmethod
    def _run(cls, *args):
        proc = subprocess.run(args, cwd=cls.root, timeout=30,
                              text=True, capture_output=True)
        if proc.returncode:
            raise AssertionError("OpenSSL local TSA failed: " + proc.stderr)
        return proc

    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tempdir.name)
        cls.root.joinpath("tsa.ext").write_text(
            "basicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature\n"
            "extendedKeyUsage=critical,timeStamping\n"
            "subjectKeyIdentifier=hash\n"
            "authorityKeyIdentifier=keyid,issuer\n",
            encoding="ascii")
        cls._run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                 "-keyout", "ca.key", "-out", "ca.pem", "-days", "2",
                 "-subj", "/CN=PRISM synthetic full-gate test CA",
                 "-addext", "basicConstraints=critical,CA:TRUE",
                 "-addext", "keyUsage=critical,keyCertSign,cRLSign")
        cls._run("openssl", "req", "-newkey", "rsa:2048", "-nodes",
                 "-keyout", "tsa.key", "-out", "tsa.csr",
                 "-subj", "/CN=PRISM synthetic full-gate TSA")
        cls._run("openssl", "x509", "-req", "-in", "tsa.csr", "-CA", "ca.pem",
                 "-CAkey", "ca.key", "-CAcreateserial", "-out", "tsa.pem",
                 "-days", "2", "-sha256", "-extfile", "tsa.ext")
        # Ephemeral issuer CRL: OpenSSL validates its signature and currency.
        cls.root.joinpath("index.txt").write_text("", encoding="ascii")
        cls.root.joinpath("crlnumber").write_text("01\n", encoding="ascii")
        cls.root.joinpath("newcerts").mkdir()
        cls.root.joinpath("ca-crl.cnf").write_text(
            "[ca]\ndefault_ca=ca_default\n[ca_default]\n"
            "database=index.txt\nnew_certs_dir=newcerts\n"
            "certificate=ca.pem\nprivate_key=ca.key\n"
            "serial=serial-ca\ncrlnumber=crlnumber\n"
            "default_md=sha256\ndefault_days=2\ndefault_crl_days=2\n"
            "policy=policy_any\n[policy_any]\ncommonName=supplied\n",
            encoding="ascii")
        cls.root.joinpath("serial-ca").write_text("01\n", encoding="ascii")
        cls._run("openssl", "ca", "-config", "ca-crl.cnf", "-gencrl",
                 "-out", "issuer.crl.pem")
        cls.crl = cls.root.joinpath("issuer.crl.pem").read_bytes()
        cls.root.joinpath("serial.txt").write_text("01\n", encoding="ascii")
        cls.root.joinpath("tsa.cnf").write_text(
            "[tsa]\ndefault_tsa=cfg\n[cfg]\nserial=serial.txt\n"
            "signer_cert=tsa.pem\nsigner_key=tsa.key\nsigner_digest=sha256\n"
            "default_policy=1.2.3.4.5\ndigests=sha256\n"
            "accuracy=secs:1\nordering=yes\ntsa_name=yes\n"
            "ess_cert_id_chain=no\n", encoding="ascii")
        cls.now = datetime.now(timezone.utc)
        cls.source = cls.now - timedelta(minutes=3)
        cls.saved = cls.now - timedelta(minutes=2)
        cls.off = cls.now + timedelta(hours=1)
        cls.entries = [{"horse_no": 1, "horse_name": "SYNTHETIC A"},
                       {"horse_no": 2, "horse_name": "SYNTHETIC B"}]
        snapshot = {"race_id": "SIM-E2E-NOT-OFFICIAL",
                    "entries": cls.entries,
                    "available_at": cls.source.isoformat()}
        ticket = {"bet_type": "単勝", "selection": [1], "stake_yen": 100}
        pick = {"mark": "◎", "horse_no": 1, "horse_name": "SYNTHETIC A"}
        cls.forecast = {
            "race_id": "SIM-E2E-NOT-OFFICIAL",
            "source_as_of": cls.source.isoformat(),
            "saved_at": cls.saved.isoformat(),
            "scheduled_off": cls.off.isoformat(),
            "forecast_version": "unit-v1",
            "input_snapshot": snapshot,
            "input_hash": digest(snapshot),
            "results_exposed": False,
            "entries": cls.entries,
            "required_agent_ids": ["RIO"],
            "agents": [{"agent_id": "RIO", "picks": [pick], "tickets": [ticket]}],
            "editorial": {"picks": [pick], "tickets": [ticket]},
        }
        cls.raw = json.dumps(cls.forecast, ensure_ascii=False,
                             sort_keys=True, separators=(",", ":")).encode("utf-8")
        cls.root.joinpath("forecast.json").write_bytes(cls.raw)
        cls._run("openssl", "ts", "-query", "-data", "forecast.json",
                 "-sha256", "-cert", "-out", "request.tsq")
        cls._run("openssl", "ts", "-reply", "-config", "tsa.cnf",
                 "-queryfile", "request.tsq", "-out", "reply.tsr")
        cls.tsq = cls.root.joinpath("request.tsq").read_bytes()
        cls.tsr = cls.root.joinpath("reply.tsr").read_bytes()
        cls.ca = cls.root.joinpath("ca.pem").read_bytes()
        cls.object_url = ("s3-version:synthetic/pre/forecast.json"
                          "?versionId=v1")
        cls.receipt = verify_rfc3161_receipt(
            cls.raw, cls.raw, cls.tsr, cls.ca, cls.object_url,
            request_der=cls.tsq, trusted_crl_pem=cls.crl)

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def setUp(self):
        self.s3 = SimulatedS3(self.raw, self.now + timedelta(days=30))
        self.context = {
            "s3_client": self.s3, "bucket": "synthetic",
            "key_prefix": "pre/", "tsa_ca_pem": self.ca,
            "tsa_crl_pem": self.crl,
            "tsa_policy_oid": "1.2.3.4.5",
            "official_race_id": self.forecast["race_id"],
            "official_scheduled_off": self.forecast["scheduled_off"],
            "official_entries": self.entries,
            "official_as_of": self.source.isoformat(),
            "official_result_exposed": False, "official_race_cancelled": False,
        }
        self.proof = {
            "forecast_bytes": self.raw, "key": "pre/forecast.json",
            "version_id": "v1", "tsa_response_der": self.tsr,
            "tsa_request_der": self.tsq,
        }
        self.result = {
            "race_id": self.forecast["race_id"],
            "retrieved_at": (self.off + timedelta(minutes=10)).isoformat(),
            "official_source": "SYNTHETIC-UNIT-TEST-NOT-OFFICIAL",
            "ticket_outcomes": {"単勝:1": {"status": "won", "payout_yen": 320}},
        }
        self.audit_at = (self.off + timedelta(hours=1)).isoformat()

    def test_real_crypto_plus_s3_mock_pre_gate(self):
        checked = validate_forecast(self.forecast, self.receipt, self.proof,
                                    verifier_context=self.context)
        self.assertEqual(checked["errors"], [])
        self.assertTrue(checked["complete"])

    def test_real_crypto_plus_s3_mock_to_synthetic_settlement(self):
        out = settle_verified_pre(self.forecast, self.receipt, self.result,
                                  self.audit_at, proof_bundle=self.proof,
                                  verifier_context=self.context)
        self.assertEqual(out["status"], "SETTLED")
        self.assertEqual(out["by_agent"]["RIO"]["roi_pct_ex_refund"], 320)
        self.assertEqual(out["by_agent"]["EDITORIAL"]["stake_yen"], 100)

    def test_s3_tampering_rejects_pre_and_settlement(self):
        self.s3.raw = self.raw + b"evil"
        out = settle_verified_pre(self.forecast, self.receipt, self.result,
                                  self.audit_at, proof_bundle=self.proof,
                                  verifier_context=self.context)
        self.assertEqual(out["status"], "PRE_LOCK_FAILED")
        self.assertTrue(any("PERSISTENCE_READBACK_FAILED" in e
                            for e in out["errors"]))

    def test_late_result_or_unadjudicated_ticket_never_settles(self):
        late = dict(self.result, retrieved_at=self.saved.isoformat())
        out = settle_verified_pre(self.forecast, self.receipt, late,
                                  self.audit_at, proof_bundle=self.proof,
                                  verifier_context=self.context)
        self.assertEqual(out["status"], "INVALID_RESULT_TIME")
        absent = dict(self.result, ticket_outcomes={})
        out = settle_verified_pre(self.forecast, self.receipt, absent,
                                  self.audit_at, proof_bundle=self.proof,
                                  verifier_context=self.context)
        self.assertEqual(out["status"], "SETTLEMENT_INCOMPLETE")

    def test_real_signed_token_with_wrong_policy_rejected(self):
        self.context["tsa_policy_oid"] = "1.2.3.4.6"
        checked = validate_forecast(self.forecast, self.receipt, self.proof,
                                    verifier_context=self.context)
        self.assertFalse(checked["complete"])
        self.assertTrue(any("RFC3161_POLICY_MISMATCH" in e
                            for e in checked["errors"]))

    def test_missing_trusted_tsa_policy_rejected(self):
        del self.context["tsa_policy_oid"]
        checked = validate_forecast(self.forecast, self.receipt, self.proof,
                                    verifier_context=self.context)
        self.assertFalse(checked["complete"])
        self.assertTrue(any("TRUSTED_VERIFIER_CONFIG_INCOMPLETE" in e
                            for e in checked["errors"]))

    def test_unverified_official_roster_rejects(self):
        self.context["official_entries"] = []
        checked = validate_forecast(self.forecast, self.receipt, self.proof,
                                    verifier_context=self.context)
        self.assertFalse(checked["complete"])
        self.assertTrue(any("OFFICIAL_ENTRIES_UNAVAILABLE" in e
                            for e in checked["errors"]))


if __name__ == "__main__":
    unittest.main()
