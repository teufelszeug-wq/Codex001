"""Synthetic readiness accounting regression tests."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))
from prism_ops.run_readiness import audit_run

NOW="2026-11-07T02:00:00+09:00"
class ReadinessTests(unittest.TestCase):
    def test_unknown_denominator(self):
        self.assertIsNone(audit_run([],NOW)["official_race_denominator"])
    def test_no_false_zero(self):
        self.assertFalse(audit_run([],NOW)["official_denominator_verified"])
    def test_unique_race_count(self):
        with patch("prism_ops.run_readiness.snapshot_gate",return_value={"verified_pre":True,"errors":[],"sha256":"abc"}):
            rows=[{"forecast":{"race_id":"r1"}},{"forecast":{"race_id":"r1"}}]
            out=audit_run([],NOW,rows,official_denominator=12)
        self.assertEqual(out["verified_pre_count"],1)
        self.assertEqual(out["unverified_pre"][0]["errors"],["DUPLICATE_VERIFIED_RACE_VERSION"])
    def test_missing_race_id(self):
        self.assertEqual(audit_run([],NOW,[{"forecast":{}}])["unverified_pre"][0]["errors"],["RACE_ID_MISSING"])
    def test_trusted_proof_and_context_forwarded(self):
        proof = {"forecast_bytes": b"real-immutable-payload", "version_id": "v1"}
        context = {"official_race_id": "r1", "key_prefix": "pre/"}
        saved = [{"forecast": {"race_id": "r1"},
                  "receipt": {"immutable_location": "s3-version:x"},
                  "proof_bundle": proof}]
        with patch("prism_ops.run_readiness.snapshot_gate",
                   return_value={"verified_pre": True, "errors": [], "sha256": "abc"}) as gate:
            result = audit_run([], NOW, saved, official_denominator=1,
                               trusted_verifier_contexts={"r1": context})
        self.assertEqual(result["verified_pre_count"], 1)
        self.assertIs(gate.call_args.kwargs["proof_bundle"], proof)
        self.assertIs(gate.call_args.kwargs["verifier_context"], context)

    def test_untrusted_item_cannot_set_verifier_context(self):
        producer_context = {"s3_client": "attacker"}
        saved = [{"forecast": {"race_id": "r1"}, "verifier_context": producer_context}]
        with patch("prism_ops.run_readiness.snapshot_gate",
                   return_value={"verified_pre": False, "errors": ["PROOF_MISSING"],
                                 "sha256": "abc"}) as gate:
            audit_run([], NOW, saved)
        self.assertIsNone(gate.call_args.kwargs["verifier_context"])

    def test_invalid_denominator(self):
        self.assertIsNone(audit_run([],NOW,official_denominator=True)["official_race_denominator"])
    def test_exceeds_denominator(self):
        with patch("prism_ops.run_readiness.snapshot_gate",return_value={"verified_pre":True,"errors":[],"sha256":"abc"}):
            with self.assertRaisesRegex(ValueError,"PRE_COUNT_EXCEEDS_DENOMINATOR"):
                audit_run([],NOW,[{"forecast":{"race_id":"r1"}}],official_denominator=0)
if __name__=="__main__":unittest.main()
