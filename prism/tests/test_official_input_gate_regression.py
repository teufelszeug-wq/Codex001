"""Regression tests for official racecard identity and time gates."""
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from scripts.assemble_official_engine_input import assemble_engine_input

def ts(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def card(numbers):
    return {
        "schema": "prism.official_racecard/v1",
        "source_verified": True,
        "race_id": "TEST-20261118-01",
        "off_at": "2026-11-18T12:00:00+09:00",
        "captured_at": "2026-11-17T12:00:00+09:00",
        "official_url": "https://example.invalid/official",
        "active_runners": [
            {"horse_no": n, "horse_name": f"horse-{i}", "frame_no": 1}
            for i, n in enumerate(numbers)
        ],
    }

def evidence(numbers):
    return {
        str(n): {
            "horse_id": f"id-{n}",
            "source_url": "https://example.invalid/history",
            "available_at": "2026-11-17T11:00:00+09:00",
            "carried_weight": 55,
            "history": [{"available_at": "2026-11-16T11:00:00+09:00"}],
        }
        for n in numbers
    }

def run(c, e):
    return assemble_engine_input(
        c, e, venue="TEST", surface="turf", distance_m=1600,
        direction="right", class_rating=1, barrier_count=8,
        locked_at="2026-11-17T18:00:00+09:00"
    )

class OfficialInputGateTests(unittest.TestCase):
    def test_duplicate_horse_number_rejected(self):
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "duplicate horse number"):
                run(card([1, 1]), evidence([1]))

    def test_future_history_rejected(self):
        e = evidence([1])
        e["1"]["history"][0]["available_at"] = "2026-11-18T13:00:00+09:00"
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "history observation from future"):
                run(card([1]), e)

    def test_missing_history_availability_rejected(self):
        e = evidence([1])
        del e["1"]["history"][0]["available_at"]
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "availability timestamp required"):
                run(card([1]), e)

    def test_racecard_identity_override_rejected(self):
        e = evidence([1])
        e["1"]["horse_no"] = 99
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "overrides racecard fields"):
                run(card([1]), e)

    def test_future_evidence_envelope_rejected(self):
        e = evidence([1])
        e["1"]["available_at"] = "2026-11-18T13:00:00+09:00"
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "horse evidence from future"):
                run(card([1]), e)


    def test_future_occurrence_rejected_even_if_availability_is_backdated(self):
        e = evidence([1])
        e["1"]["history"][0]["occurred_at"] = "2026-11-18T13:00:00+09:00"
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "availability precedes occurrence"):
                run(card([1]), e)

    def test_future_occurrence_rejected_with_timely_availability(self):
        e = evidence([1])
        e["1"]["history"][0]["occurred_at"] = "2026-11-18T13:00:00+09:00"
        e["1"]["history"][0]["available_at"] = "2026-11-18T14:00:00+09:00"
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "history observation from future"):
                run(card([1]), e)

    def test_optional_feature_after_lock_rejected(self):
        e = evidence([1, 2])
        e["1"]["workout"] = {"score": 80, "available_at": "2026-11-17T19:00:00+09:00"}
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "feature from future relative to prediction lock"):
                run(card([1, 2]), e)

    def test_optional_feature_without_availability_rejected(self):
        e = evidence([1, 2])
        e["1"]["workout"] = {"score": 80}
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "feature availability timestamp required"):
                run(card([1, 2]), e)

    def test_optional_feature_future_observation_backdated_availability_rejected(self):
        e = evidence([1, 2])
        e["1"]["workout"] = {
            "score": 80,
            "available_at": "2026-11-17T17:00:00+09:00",
            "observed_at": "2026-11-17T19:00:00+09:00",
        }
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "feature observation from future"):
                run(card([1, 2]), e)

    def test_optional_feature_availability_before_occurrence_rejected(self):
        e = evidence([1, 2])
        e["1"]["workout"] = {
            "score": 80,
            "available_at": "2026-11-17T16:00:00+09:00",
            "occurred_at": "2026-11-17T17:00:00+09:00",
        }
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "feature availability precedes occurrence"):
                run(card([1, 2]), e)

    def test_optional_feature_availability_before_observation_rejected(self):
        e = evidence([1, 2])
        e["1"]["workout"] = {
            "score": 80,
            "available_at": "2026-11-17T16:00:00+09:00",
            "observed_at": "2026-11-17T17:00:00+09:00",
        }
        with patch("scripts.assemble_official_engine_input.timestamp", side_effect=ts):
            with self.assertRaisesRegex(ValueError, "feature availability precedes occurrence"):
                run(card([1, 2]), e)

    def test_valid_two_runner_input_reaches_contract(self):
        """Positive control: valid evidence must produce an engine input, not just reject bad cases."""
        c = card([1, 2])
        e = evidence([1, 2])
        for number in ("1", "2"):
            e[number]["history"] = [{
                "occurred_at": "2026-11-10T12:00:00+09:00",
                "available_at": "2026-11-10T15:00:00+09:00",
                "performance_score": 65,
                "distance_m": 1600,
                "surface": "TURF",
                "direction": "RIGHT",
                "class_rating": 1,
                "venue": "TEST",
            }]
        raw, names = assemble_engine_input(
            c, e, venue="TEST", surface="TURF", distance_m=1600,
            direction="RIGHT", class_rating=1, barrier_count=8,
            locked_at="2026-11-17T18:00:00+09:00"
        )
        self.assertEqual(raw["mode"], "PRE_AVAILABLE")
        self.assertEqual(len(raw["runners"]), 2)
        self.assertEqual(len(names), 2)

if __name__ == "__main__":
    unittest.main()
