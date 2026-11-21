"""End-to-end preday pipeline contract test with deterministic local fixtures.

Run: python -m unittest prism.tests.test_preday_pipeline_e2e -v
These synthetic fixtures are NOT official racecards or real forecasts.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from prism.preday_pipeline_cli import run


class PredayPipelineE2ETest(unittest.TestCase):
    def test_synthetic_full_field_save_and_no_overwrite(self):
        jst = timezone(timedelta(hours=9))
        # Future race date, with an actual preday write time (now).
        now = datetime.now(timezone.utc)
        race_day = now.astimezone(jst).date() + timedelta(days=2)
        start = datetime.combine(race_day, datetime.min.time(), jst) + timedelta(hours=12)
        racecard = {
            "race_id": "SYNTHETIC_001",
            "source_id": "TEST_FIXTURE_NOT_OFFICIAL",
            "source_authenticity_verified": True,
            "source_retrieved_at": (now - timedelta(minutes=1)).isoformat(),
            "scheduled_start_at": start.isoformat(),
            "horses": [
                {"horse_id": "h1", "horse_name": "試験馬一"},
                {"horse_id": "h2", "horse_name": "試験馬二"},
            ],
        }
        forecasts = [
            {"horse_id": "h1", "prediction": {"win_probability": 0.6}},
            {"horse_id": "h2", "prediction": {"win_probability": 0.4}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            card = root / "racecard.json"
            predictions = root / "forecasts.json"
            card.write_text(json.dumps(racecard, ensure_ascii=False), encoding="utf-8")
            predictions.write_text(json.dumps(forecasts, ensure_ascii=False), encoding="utf-8")
            args = (card, predictions, root / "out", "synthetic_forecaster", "v1")
            result = run(*args)
            self.assertEqual(result["runner_count"], 2)
            stored = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
            self.assertEqual({r["horse_name"] for r in stored}, {"試験馬一", "試験馬二"})
            self.assertEqual({r["race_id"] for r in stored}, {"SYNTHETIC_001"})
            with self.assertRaises(FileExistsError):
                run(*args)

    def test_incomplete_forecast_does_not_write(self):
        jst = timezone(timedelta(hours=9))
        now = datetime.now(timezone.utc)
        start = now.astimezone(jst) + timedelta(days=2)
        card = {"race_id": "SYNTHETIC_002", "source_id": "TEST_ONLY",
                "source_authenticity_verified": True,
                "scheduled_start_at": start.isoformat(),
                "horses": [{"horse_id": "a", "horse_name": "試験甲"},
                           {"horse_id": "b", "horse_name": "試験乙"}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "c.json").write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
            (root / "f.json").write_text(json.dumps([
                {"horse_id": "a", "prediction": {"win_probability": 1.0}}
            ]), encoding="utf-8")
            with self.assertRaises(ValueError):
                run(root / "c.json", root / "f.json", root / "out", "tester", "v1")
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
