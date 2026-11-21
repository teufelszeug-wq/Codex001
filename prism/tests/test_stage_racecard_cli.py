import json
import tempfile
import unittest
from pathlib import Path
from stage_racecard_cli import stage_file


class TestStage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "raw.json"
        self.target = Path(self.tmp.name) / "staged.json"
        self.source.write_text(json.dumps({
            "race_id": "SAMPLE",
            "scheduled_start_at": "2099-01-01T12:00:00+09:00",
            "horses": [{"horse_id": "1", "horse_name": "架空馬"}]
        }), encoding="utf-8")
        self.args = {
            "source_url": "https://example.org/sample",
            "retrieved_at": "2026-11-20T10:00:00+09:00",
            "race_id": "SAMPLE"
        }

    def test_stages_without_authenticating(self):
        result = stage_file(self.source, self.target, **self.args)
        self.assertFalse(result["source_authenticity_verified"])
        self.assertEqual(json.loads(self.target.read_text())["race_id"], "SAMPLE")

    def test_no_overwrite(self):
        stage_file(self.source, self.target, **self.args)
        with self.assertRaises(FileExistsError):
            stage_file(self.source, self.target, **self.args)

    def test_no_source_overwrite(self):
        with self.assertRaises(ValueError):
            stage_file(self.source, self.source, **self.args)

    def test_reject_post_start(self):
        self.args["retrieved_at"] = "2099-01-02T10:00:00+09:00"
        with self.assertRaises(ValueError):
            stage_file(self.source, self.target, **self.args)
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
