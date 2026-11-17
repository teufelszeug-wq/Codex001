"""Regression tests for append-only pre-race prediction snapshots."""
import tempfile
import unittest
from pre_race_store import append_prediction

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = dict(race_id="R1", horse_name="テスト馬", predictor_id="paper", source="official", saved_at="2026-11-17T09:00:00+09:00", off_at="2026-11-18T15:00:00+09:00", version="previous_day/v1", kind="pre_race", evidence=[dict(available_at="2026-11-17T08:00:00+09:00")])
    def save(self, data=None, now="2026-11-17T09:01:00+09:00"):
        return append_prediction(self.tmp.name, data or self.base, now=now)
    def test_create(self):
        self.assertTrue(self.save().exists())
    def test_duplicate_refused(self):
        self.save()
        with self.assertRaises(FileExistsError): self.save()
    def test_late_refused(self):
        with self.assertRaises(ValueError): self.save(now="2026-11-18T15:00:00+09:00")
    def test_future_saved_refused(self):
        with self.assertRaises(ValueError): self.save(now="2026-11-17T08:00:00+09:00")
    def test_future_evidence_refused(self):
        d=dict(self.base, evidence=[dict(available_at="2026-11-17T10:00:00+09:00")])
        with self.assertRaises(ValueError): self.save(d)
    def test_backdated_evidence_refused(self):
        d=dict(self.base, evidence=[dict(available_at="2026-11-17T08:00:00+09:00", observed_at="2026-11-17T08:30:00+09:00")])
        with self.assertRaises(ValueError): self.save(d)
    def test_review_refused(self):
        with self.assertRaises(ValueError): self.save(dict(self.base, kind="post_race_review"))
    def test_naive_time_refused(self):
        with self.assertRaises(ValueError): self.save(dict(self.base, saved_at="2026-11-17T09:00:00"))

if __name__ == "__main__":
    unittest.main()
