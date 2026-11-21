"""Regression tests for the reviewed-input preday CLI integration."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prism.preday_pipeline_cli import run


class PipelineCLITests(unittest.TestCase):
    def test_unverified_source_rejected_before_forecast(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "card.json").write_text(json.dumps({"source_authenticity_verified": False}))
            (base / "forecasts.json").write_text("[]")
            with patch("prism.preday_pipeline_cli.build_preday_records") as build:
                with self.assertRaisesRegex(ValueError, "authentication"):
                    run(base / "card.json", base / "forecasts.json", base, "editor", "v1")
                build.assert_not_called()

    def test_bridge_to_store_and_output_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "card.json").write_text(json.dumps({
                "source_authenticity_verified": True, "race_id": "race1"}))
            (base / "forecasts.json").write_text("[]")
            records = [{"horse_id": "h1"}]
            with patch("prism.preday_pipeline_cli.build_preday_records", return_value=records) as build:
                with patch("prism.preday_pipeline_cli.persist_preday_batch", return_value="saved.json") as store:
                    result = run(base / "card.json", base / "forecasts.json", base, "editor", "v1")
            build.assert_called_once()
            store.assert_called_once_with(records, base)
            self.assertEqual(result["runner_count"], 1)
            self.assertEqual(result["path"], "saved.json")


if __name__ == "__main__":
    unittest.main()
