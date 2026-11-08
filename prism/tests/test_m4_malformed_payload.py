"""Malformed producer data must fail closed, never crash the M4 runner."""
import copy
import unittest
from prism_ops.forecast_completion_gate import digest, validate_forecast


def sample():
    entries = [{"horse_no": 1, "horse_name": "synthetic"}]
    snapshot = {"race_id": "SIM-MALFORMED", "entries": entries}
    agent = {"agent_id": "RIO",
             "picks": [{"mark": "◎", "horse_no": 1, "horse_name": "synthetic"}],
             "tickets": [{"bet_type": "単勝", "selection": [1], "stake_yen": 100}]}
    return {
        "race_id": "SIM-MALFORMED",
        "scheduled_off": "2099-11-08T12:00:00+09:00",
        "saved_at": "2099-11-08T10:00:00+09:00",
        "source_as_of": "2099-11-08T09:59:00+09:00",
        "forecast_version": "synthetic-v1",
        "input_snapshot": snapshot, "input_hash": digest(snapshot),
        "results_exposed": False, "entries": entries,
        "required_agent_ids": ["RIO"], "agents": [agent],
        "editorial": {"picks": copy.deepcopy(agent["picks"]),
                      "tickets": copy.deepcopy(agent["tickets"])},
    }


class MalformedPayloadTests(unittest.TestCase):
    def test_non_dict_forecast_rejected(self):
        for forecast in (None, [], "bad", 12):
            with self.subTest(value=forecast):
                r = validate_forecast(forecast)
                self.assertFalse(r["complete"])
                self.assertIn("INVALID_FORECAST", r["errors"])

    def test_malformed_runner_records_rejected(self):
        cases = (None, {"horse_no": 1}, [123],
                 [{"horse_no": [1], "horse_name": "synthetic"}],
                 [{"horse_no": 1, "horse_name": ["synthetic"]}])
        for entries in cases:
            with self.subTest(entries=entries):
                f = sample()
                f["entries"] = entries
                r = validate_forecast(f)
                self.assertFalse(r["complete"])
                self.assertTrue(any(x in r["errors"] for x in
                                    ("INVALID_ENTRIES", "INVALID_HORSE_NUMBER")))

    def test_malformed_agents_and_roster_rejected(self):
        cases = (
            ("agents", None),
            ("agents", [123]),
            ("required_agent_ids", [{"id": "RIO"}]),
            ("agents", [dict(sample()["agents"][0], agent_id={"id": "RIO"})]),
            ("agents", [dict(sample()["agents"][0], picks=["not-a-pick"])]),
            ("agents", [dict(sample()["agents"][0],
                             picks=[{"mark": "◎", "horse_no": [1],
                                     "horse_name": "synthetic"}])]),
            ("agents", [dict(sample()["agents"][0], tickets=["invalid"])]),
            ("agents", [dict(sample()["agents"][0],
                             tickets=[{"bet_type": "単勝", "selection": [[1]],
                                       "stake_yen": 100}])]),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                f = sample()
                f[field] = value
                r = validate_forecast(f)
                self.assertFalse(r["complete"])
                self.assertTrue(any("INVALID_" in x for x in r["errors"]))

    def test_malformed_editorial_evidence_and_stake_rejected(self):
        changes = (
            ("editorial", "not-dict", "INVALID_EDITORIAL"),
            ("evidence", {"source": "wrong-list"}, "INVALID_EVIDENCE"),
            ("evidence", ["bad"], "INVALID_EVIDENCE"),
        )
        for field, value, error in changes:
            f = sample()
            f[field] = value
            self.assertIn(error, validate_forecast(f)["errors"])
        f = sample()
        f["agents"][0]["tickets"][0]["stake_yen"] = True
        self.assertIn("RIO:STAKE_NOT_100", validate_forecast(f)["errors"])


if __name__ == "__main__":
    unittest.main()
