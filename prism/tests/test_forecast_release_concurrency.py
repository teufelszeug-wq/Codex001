"""Regression: concurrent releases of the same version must not both succeed."""
import json
import sys
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from forecast_release import release


def publish(pair):
    try:
        return release(*pair)[2], None
    except ValueError as exc:
        return False, str(exc)


class ConcurrentReleaseTest(unittest.TestCase):
    def test_conflicting_payloads_only_one_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {
                "race_id": "20261117_TEST_01",
                "saved_at": "2026-11-16T10:00:00+09:00",
                "off_at": "2026-11-17T12:00:00+09:00",
                "source_refs": ["fixture:test"],
                "version": 1,
                "records": [{"forecaster_id": "RIO", "decision": "abstain"}],
            }
            inputs = []
            for i in range(12):
                p = root / f"input_{i}.json"
                d = dict(payload)
                d["source_refs"] = [f"fixture:test:{i}"]
                p.write_text(json.dumps(d), encoding="utf-8")
                inputs.append((str(p), str(root / "releases")))
            with ProcessPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(publish, inputs))
            self.assertEqual(sum(created for created, _ in results), 1)
            self.assertEqual(sum(err is not None for _, err in results), 11)
            self.assertEqual(len(list((root / "releases" / payload["race_id"]).glob("v1-*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
