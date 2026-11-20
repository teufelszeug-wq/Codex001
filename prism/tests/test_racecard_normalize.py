"""Regression tests for captured racecard normalization; synthetic fixtures only."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from prism_engine.racecard_normalize import normalize_candidate

class NormalizeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source, self.meta = root / "source", root / "meta.json"
        self.card = {"race_id": "SYNTHETIC-R1", "runners": [
            {"horse_id": "h1", "horse_name": "架空一号", "horse_number": 1},
            {"horse_id": "h2", "horse_name": "架空二号", "horse_number": 2}]}
        self.write()

    def write(self):
        raw = json.dumps(self.card, ensure_ascii=False).encode()
        self.source.write_bytes(raw)
        self.meta.write_text(json.dumps({"schema": "prism.source.capture/v1",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "final_url": "https://www.jra.go.jp/",
            "source_authenticity_verified": False}))

    def test_normal(self):
        record = normalize_candidate(self.source, self.meta)
        self.assertEqual(record["runners"][0]["horse_name"], "架空一号")
        self.assertFalse(record["source_authenticity_verified"])

    def test_tamper(self):
        self.source.write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "digest"):
            normalize_candidate(self.source, self.meta)

    def test_duplicate_number(self):
        self.card["runners"][1]["horse_number"] = 1
        self.write()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            normalize_candidate(self.source, self.meta)

    def test_html_rejected(self):
        raw = b"<html>race</html>"
        self.source.write_bytes(raw)
        self.meta.write_text(json.dumps({"schema": "prism.source.capture/v1",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source_authenticity_verified": False}))
        with self.assertRaisesRegex(ValueError, "HTML unsupported"):
            normalize_candidate(self.source, self.meta)

    def test_authenticity_claim_rejected(self):
        meta = json.loads(self.meta.read_text())
        meta["source_authenticity_verified"] = True
        self.meta.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, "unverified"):
            normalize_candidate(self.source, self.meta)
