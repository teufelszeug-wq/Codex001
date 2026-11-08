"""Contract tests for the PRISM forecast completion gate. Synthetic fixtures only."""
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from prism_ops.forecast_completion_gate import validate_forecast, settle_forecast, digest

def fixture():
    snapshot = {"race_id":"synthetic-race","inputs":"test"}
    return {"input_snapshot": snapshot, "input_hash": digest(snapshot),
      "forecast_version": "synthetic-v1", "source_as_of": "2026-11-06T12:00:00+09:00",
      "results_exposed": False,"race_id":"synthetic-race","saved_at":"2026-11-06T19:00:00+09:00",
      "scheduled_off":"2026-11-07T15:00:00+09:00",
      "entries":[{"horse_no":1,"horse_name":"架空A"},{"horse_no":2,"horse_name":"架空B"}],
      "required_agent_ids":["rio"],"agents":[{"agent_id":"rio","picks":[{"mark":"◎","horse_no":1,"horse_name":"架空A"}],
        "tickets":[{"bet_type":"単勝","selection":[1],"stake_yen":100}]}],
      "editorial":{"picks":[{"mark":"◎","horse_no":2,"horse_name":"架空B"}],"tickets":[],"pass_reason":"見送り"},
      "evidence":[{"kind":"form","source":"synthetic fixture","available_at":"2026-11-06T12:00:00+09:00"}]}

class ForecastGateTests(unittest.TestCase):
    def test_valid_shape_does_not_bypass_external_proof(self):
        result = validate_forecast(fixture())
        self.assertFalse(result["complete"])
        self.assertIn("CRYPTOGRAPHIC_PROOF_BUNDLE_MISSING", result["errors"])
        self.assertNotIn("INVALID_ENTRIES", result["errors"])
        self.assertNotIn("rio:INVALID_PICKS", result["errors"])
    def test_no_ticket(self):
        f=fixture(); f["agents"][0]["tickets"]=[]
        self.assertFalse(validate_forecast(f)["complete"])
    def test_late_lock(self):
        f=fixture(); f["saved_at"]="2026-11-07T16:00:00+09:00"
        self.assertFalse(validate_forecast(f)["complete"])
    def test_future_evidence(self):
        f=fixture(); f["evidence"][0]["available_at"]="2026-11-07T14:00:00+09:00"
        self.assertFalse(validate_forecast(f)["complete"])
    def test_100_yen(self):
        f=fixture(); f["agents"][0]["tickets"][0]["stake_yen"]=200
        self.assertFalse(validate_forecast(f)["complete"])
    def test_roster_missing(self):
        f=fixture(); del f["required_agent_ids"]
        self.assertIn("REQUIRED_AGENT_ROSTER_MISSING",validate_forecast(f)["errors"])
    def test_roster_incomplete(self):
        f=fixture(); f["required_agent_ids"].append("pace")
        self.assertIn("AGENT_COVERAGE_INCOMPLETE",validate_forecast(f)["errors"])
    def test_duplicate_ticket(self):
        f=fixture(); f["agents"][0]["tickets"].append(dict(f["agents"][0]["tickets"][0]))
        self.assertIn("rio:DUPLICATE_TICKET",validate_forecast(f)["errors"])
    def test_roi(self):
        # Synthetic accounting unit test; the M4 proof gate is separately tested.
        with patch("prism_ops.forecast_completion_gate.validate_forecast",
                   return_value={"complete":True,"errors":[],"sha256":digest(fixture())}):
            r=settle_forecast(fixture(),{"race_id":"synthetic-race","official_source":"synthetic fixture",
               "ticket_outcomes":{"単勝:1":{"status":"won","payout_yen":320}}})
        self.assertEqual(r["by_agent"]["rio"]["roi_pct_ex_refund"],320)
        self.assertIsNone(r["by_agent"]["EDITORIAL"]["roi_pct_ex_refund"])

if __name__=="__main__": unittest.main()
