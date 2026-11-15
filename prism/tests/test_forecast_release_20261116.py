import json
import tempfile
import unittest
from pathlib import Path
from forecast_release import release

BASE = {"race_id":"JRA-20261117-01-11","version":1,"saved_at":"2026-11-16T19:00:00+09:00","off_at":"2026-11-17T15:40:00+09:00","source_refs":["fixture-only"],"records":[{"forecaster_id":"RIO","decision":"abstain"}]}

class ReleaseTest(unittest.TestCase):
    def test_idempotent_immutable(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"input.json"; inp.write_text(json.dumps(BASE))
            a=release(inp,Path(d)/"out"); b=release(inp,Path(d)/"out")
            self.assertTrue(a[2]); self.assertFalse(b[2]); self.assertEqual(a[:2],b[:2])
    def test_version_collision_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"input.json"; inp.write_text(json.dumps(BASE))
            release(inp,Path(d)/"out")
            inp.write_text(json.dumps({**BASE,"source_refs":["different-fixture"]}))
            with self.assertRaisesRegex(ValueError,"version already published"): release(inp,Path(d)/"out")
    def test_post_off_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"input.json"; inp.write_text(json.dumps({**BASE,"saved_at":"2026-11-18T00:00:00+09:00"}))
            with self.assertRaisesRegex(ValueError,"pre_off_time"): release(inp,Path(d)/"out")
    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            inp=Path(d)/"input.json"; inp.write_text(json.dumps({**BASE,"race_id":"../escape"}))
            with self.assertRaisesRegex(ValueError,"race_id_path"): release(inp,Path(d)/"out")
    def test_bad_stake_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            doc={**BASE,"records":[{"forecaster_id":"RIO","decision":"bet","bets":[{"horse_name":"fixture","stake_yen":150}]}]}
            inp=Path(d)/"input.json"; inp.write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError,"stake_yen"): release(inp,Path(d)/"out")
if __name__=="__main__": unittest.main()
