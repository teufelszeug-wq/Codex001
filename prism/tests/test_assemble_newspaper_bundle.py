"""Regression tests for evidence-backed newspaper bundle assembly."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from assemble_newspaper_bundle import assemble

RACE = "20261123-JRA-TOKYO-11"


class AssembleBundleTests(unittest.TestCase):
    def test_missing_source_does_not_invent_newspaper(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                assemble(Path(tmp), RACE)

    def test_saved_forecast_and_five_topics_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / RACE
            folder.mkdir()
            (folder / "racecard.json").write_text(json.dumps({
                "race_id": RACE, "race_name": "検証競走", "off_at": "2026-11-23T15:30:00+09:00",
                "runners": [{"horse_no": 1, "horse_name": "架空試験馬", "frame_no": 1, "horse_id": "2020000001"}]
            }), encoding="utf-8")
            final_payload = {
                "race_id": RACE, "saved_at": "2026-11-22T18:00:00+09:00",
                "metadata": {"phase": "FINAL", "model_backend": "local_rules"},
                "records": [{"forecaster_id": "HONSHI", "display_name": "本紙",
                             "diagnoses": [{"horse_no": 1, "reason": "人工試験用"}],
                             "picks": [{"horse_no": 1, "mark": "◎"}],
                             "tickets": [{"type": "WIN", "horse_nos": [1], "stake_yen": 100}]}]
            }
            (folder / "v2.json").write_text(json.dumps(final_payload), encoding="utf-8")
            preliminary_payload = {**final_payload, "saved_at": "2026-11-22T16:00:00+09:00",
                                   "metadata": {"phase": "PRELIMINARY", "model_backend": "local_rules"}}
            (folder / "v1.json").write_text(json.dumps(preliminary_payload), encoding="utf-8")
            (folder / "roundtable-v1.json").write_text(json.dumps({
                "race_id": RACE, "opened_at": "2026-11-22T17:00:00+09:00",
                "recorded_at": "2026-11-22T17:30:00+09:00",
                "facilitator_id": "PRISM-EDITOR-01",
                "topics": [{"id": str(n), "title": "議題" + str(n),
                            "turns": [{"speaker_id": "HONSHI", "text": "人工議論" + str(n)}]}
                           for n in range(5)]
            }), encoding="utf-8")
            result = assemble(Path(tmp), RACE)
            self.assertEqual(len(result["discussions"]), 5)
            self.assertEqual(result["race"]["runners"][0]["name"], "架空試験馬")
            self.assertEqual(result["final"]["HONSHI"]["tickets"][0]["stake_yen"], 100)
            self.assertEqual(result["mode"], "single_model_simulation")
            preliminary_path = folder / "v1.json"
            preliminary_payload["records"] = []
            preliminary_path.write_text(json.dumps(preliminary_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "forecaster roster mismatch"):
                assemble(Path(tmp), RACE)
            preliminary_payload["records"] = final_payload["records"].copy()
            preliminary_path.write_text(json.dumps(preliminary_payload), encoding="utf-8")
            self.assertEqual(result["race"]["runners"][0]["horse_id"], "2020000001")
            self.assertEqual(result["final"]["HONSHI"]["diagnoses"][0]["horse_id"], "2020000001")
            self.assertEqual(result["preliminary"]["HONSHI"]["saved_at"], "2026-11-22T16:00:00+09:00")
            self.assertEqual(result["final"]["HONSHI"]["saved_at"], "2026-11-22T18:00:00+09:00")
            discussion_path = folder / "roundtable-v1.json"
            discussion = json.loads(discussion_path.read_text(encoding="utf-8"))
            discussion["recorded_at"] = "2026-11-22T15:59:00+09:00"
            discussion_path.write_text(json.dumps(discussion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "preliminary forecast must precede"):
                assemble(Path(tmp), RACE)
            discussion["recorded_at"] = "2026-11-22T17:30:00+09:00"
            discussion_path.write_text(json.dumps(discussion), encoding="utf-8")
            final_payload["records"].append(final_payload["records"][0])
            (folder / "v2.json").write_text(json.dumps(final_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate forecaster IDs"):
                assemble(Path(tmp), RACE)
            final_payload["records"].pop()
            (folder / "v2.json").write_text(json.dumps(final_payload), encoding="utf-8")
            discussion["topics"][1]["id"] = discussion["topics"][0]["id"]
            discussion_path.write_text(json.dumps(discussion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "topic IDs must be nonempty and unique"):
                assemble(Path(tmp), RACE)
            discussion["topics"][1]["id"] = "1"
            discussion["topics"][2]["turns"] = []
            discussion_path.write_text(json.dumps(discussion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "require attributed substantive turns"):
                assemble(Path(tmp), RACE)
            discussion["topics"][2]["turns"] = [{"speaker_id": "HONSHI", "text": "人工議論2"}]
            discussion_path.write_text(json.dumps(discussion), encoding="utf-8")
            discussion["opened_at"] = "2026-11-22T17:31:00+09:00"
            discussion_path.write_text(json.dumps(discussion), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "roundtable timestamps must be ordered"):
                assemble(Path(tmp), RACE)
            discussion["opened_at"] = "2026-11-22T17:00:00+09:00"
            discussion_path.write_text(json.dumps(discussion), encoding="utf-8")
            card_path = folder / "racecard.json"
            card = json.loads(card_path.read_text(encoding="utf-8"))
            card["captured_at"] = "2026-11-22T16:01:00+09:00"
            card_path.write_text(json.dumps(card), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "potential look-ahead leak"):
                assemble(Path(tmp), RACE)
            card["captured_at"] = "2026-11-22T15:59:00+09:00"
            card_path.write_text(json.dumps(card), encoding="utf-8")
            self.assertEqual(assemble(Path(tmp), RACE)["final"]["HONSHI"]["saved_at"], "2026-11-22T18:00:00+09:00")
            final_path = folder / "v2.json"
            final_payload["records"][0]["picks"] = [{"horse_no": 99, "mark": "◎"}]
            final_path.write_text(json.dumps(final_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown or scratched horse"):
                assemble(Path(tmp), RACE)
            final_payload["records"][0]["picks"] = [{"horse_no": 1, "mark": "◎"}, {"horse_no": 1, "mark": "○"}]
            final_path.write_text(json.dumps(final_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate horse picks"):
                assemble(Path(tmp), RACE)
            final_payload["records"][0]["picks"] = [{"horse_no": 1, "mark": "◎"}]
            final_payload["records"][0]["diagnoses"][0]["reason"] = " "
            final_path.write_text(json.dumps(final_payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "substantive reason"):
                assemble(Path(tmp), RACE)
            final_payload["records"][0]["diagnoses"][0]["reason"] = "人工試験用"
            final_path.write_text(json.dumps(final_payload), encoding="utf-8")
            self.assertEqual(len(assemble(Path(tmp), RACE)["final"]["HONSHI"]["picks"]), 1)


if __name__ == "__main__":
    unittest.main()
