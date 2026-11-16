"""Regression checks for per-observation cutoff leakage in official input assembly."""
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import sys
import types


def parse_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class HistoryCutoffTests(unittest.TestCase):
    def test_future_history_rejected_before_engine_validation(self):
        fake = types.ModuleType("prism_engine")
        contracts = types.ModuleType("prism_engine.contracts")
        contracts.timestamp = parse_timestamp
        contracts.digest = lambda data: "test-digest"
        contracts.validate = lambda data: None
        script = Path(__file__).resolve().parents[1] / "scripts" / "assemble_official_engine_input.py"
        with patch.dict(sys.modules, {"prism_engine": fake, "prism_engine.contracts": contracts}):
            spec = importlib.util.spec_from_file_location("official_adapter_cutoff_test", script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        card = {
            "schema": "prism.official_racecard/v1",
            "source_verified": True,
            "off_at": "2026-11-18T12:00:00+09:00",
            "captured_at": "2026-11-17T10:00:00+09:00",
            "race_id": "TEST-20261118-01",
            "official_url": "https://example.org/racecard",
            "active_runners": [{"horse_no": 1, "horse_name": "TEST HORSE", "frame_no": 1}],
        }
        evidence = {"1": {
            "horse_id": "TEST-H1",
            "source_url": "https://example.org/history",
            "available_at": "2026-11-17T10:00:00+09:00",
            "carried_weight": 55,
            "history": [{"race_date": "2026-11-19T00:00:00+09:00"}],
        }}
        kwargs = dict(venue="test", surface="turf", distance_m=1600,
                      direction="right", class_rating=1, barrier_count=1,
                      locked_at="2026-11-17T18:00:00+09:00")
        with self.assertRaisesRegex(ValueError, "history observation from future"):
            module.assemble_engine_input(card, evidence, **kwargs)
        evidence["1"]["history"][0]["race_date"] = "2026-11-16T00:00:00+09:00"
        raw, names = module.assemble_engine_input(card, evidence, **kwargs)
        self.assertEqual(len(raw["runners"]), 1)
        self.assertEqual(names["TEST-H1"], "TEST HORSE")


if __name__ == "__main__":
    unittest.main()
