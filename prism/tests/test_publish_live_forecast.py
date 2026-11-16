import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import sys
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publish_live_forecast import publish_live

class LivePublicationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "input.json"
        self.output = Path(self.tmp.name) / "releases"
        self.now = datetime(2026, 11, 16, 6, 0, tzinfo=timezone.utc)

    def doc(self, saved=None, off=None):
        return {"race_id": "20261117_TEST_11R", "version": 1,
                "saved_at": (saved or self.now).isoformat(),
                "off_at": (off or self.now + timedelta(days=1)).isoformat(),
                "source_refs": ["official-starters-test-fixture"],
                "records": [{"forecaster_id": "paper", "decision": "abstain"}]}

    def run_doc(self, doc):
        self.source.write_text(json.dumps(doc), encoding="utf-8")
        return publish_live(self.source, self.output, now=self.now)

    def test_live_release(self):
        result = self.run_doc(self.doc())
        self.assertTrue(result["created"])
        self.assertEqual(result["provenance"], "local_clock_only")
        self.assertTrue(Path(result["path"]).exists())

    def test_post_off_backdating_rejected(self):
        with self.assertRaisesRegex(ValueError, "already started"):
            self.run_doc(self.doc(off=self.now - timedelta(minutes=1)))

    def test_future_saved_at_rejected(self):
        with self.assertRaisesRegex(ValueError, "saved_at is in the future"):
            self.run_doc(self.doc(saved=self.now + timedelta(minutes=3)))

    def test_legacy_release_cli_rejects_post_off_backdating(self):
        # The old CLI previously bypassed publish_live and accepted stale saved_at.
        stale = self.doc(off=datetime(2020, 1, 1, tzinfo=timezone.utc))
        stale["saved_at"] = "2019-12-31T00:00:00+00:00"
        self.source.write_text(json.dumps(stale), encoding="utf-8")
        script = Path(__file__).resolve().parents[1] / "scripts" / "forecast_release.py"
        proc = subprocess.run([sys.executable, str(script), str(self.source), str(self.output)],
                              capture_output=True, text=True, timeout=10)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("race already started", proc.stderr)
        self.assertEqual(list(self.output.rglob("v*.json")) if self.output.exists() else [], [])

    def test_missing_forecaster_rejected(self):
        doc = self.doc()
        doc["records"] = [{"decision": "abstain"}]
        with self.assertRaisesRegex(ValueError, "preflight failed"):
            self.run_doc(doc)

if __name__ == "__main__":
    unittest.main()
