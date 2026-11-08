"""The production settlement wrapper must fail closed on untrusted official data."""
import unittest
from unittest.mock import patch
from prism_ops.forecast_completion_gate import digest
from prism_ops.settlement_fail_closed import settle_with_trusted_official_result


class OfficialResultTrustTests(unittest.TestCase):
    def setUp(self):
        self.forecast = {"race_id": "SIM-01",
                         "scheduled_off": "2026-11-08T12:00:00+09:00"}
        self.result = {"race_id": "SIM-01", "official_source": "official-adapter",
                       "ticket_outcomes": {}}
        self.ctx = {"verified_by": "PRISM_TRUSTED_OFFICIAL_RESULT_VERIFIER",
                    "official_final": True, "race_id": "SIM-01",
                    "official_source": "official-adapter",
                    "official_published_at": "2026-11-08T12:15:00+09:00",
                    "official_observed_at": "2026-11-08T12:16:00+09:00",
                    "official_result_sha256": digest(self.result)}

    def call(self, ctx=None, result=None):
        with patch("prism_ops.forecast_completion_gate.settle_forecast",
                   return_value={"settled": True}) as mock:
            out = settle_with_trusted_official_result(
                self.forecast, self.result if result is None else result,
                trusted_result_context=self.ctx if ctx is None else ctx)
            mock.assert_called_once()
            return out

    def test_trusted_final_result_reaches_settlement(self):
        self.assertEqual(self.call(), {"settled": True})

    def test_untrusted_source_claim_rejected(self):
        for ctx in (None, {}, {**self.ctx, "verified_by": "producer"},
                    {**self.ctx, "official_final": False},
                    {**self.ctx, "official_source": "fake"},
                    {**self.ctx, "race_id": "OTHER"}):
            with self.subTest(ctx=ctx), self.assertRaises(ValueError):
                self.call(ctx=ctx)

    def test_result_content_hash_rejected(self):
        result = {**self.result, "ticket_outcomes": {"単勝:1": {"status": "won",
                                                              "payout_yen": 999}}}
        with self.assertRaisesRegex(ValueError, "OFFICIAL_RESULT_HASH_MISMATCH"):
            self.call(result=result)

    def test_result_must_be_published_after_off(self):
        for when in ("2026-11-08T11:59:00+09:00",
                     "2026-11-08T12:00:00+09:00",
                     "invalid"):
            with self.subTest(when=when), self.assertRaises(ValueError):
                self.call(ctx={**self.ctx, "official_published_at": when})

    def test_result_cannot_be_observed_before_published(self):
        with self.assertRaisesRegex(ValueError, "OFFICIAL_RESULT_TIME_UNVERIFIED"):
            self.call(ctx={**self.ctx,
                           "official_observed_at": "2026-11-08T12:14:00+09:00"})


if __name__ == "__main__":
    unittest.main()
