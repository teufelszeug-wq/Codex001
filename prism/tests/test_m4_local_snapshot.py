"""Local-only M4 snapshot tests: never claims external timestamp verification."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from prism_ops.local_snapshot import save_local_snapshot, audit_local_snapshots

FORECAST = {"race_id": "SIM-001", "scheduled_off": "2099-11-09T10:00:00+09:00",
            "results_exposed": False, "agents": [], "entries": []}
EARLY = datetime(2099, 11, 9, 0, 0, tzinfo=timezone.utc)
LATE = datetime(2099, 11, 9, 1, 0, tzinfo=timezone.utc)

class LocalSnapshotTests(unittest.TestCase):
    def test_save_and_independent_readback(self):
        with tempfile.TemporaryDirectory() as root:
            result = save_local_snapshot(root, FORECAST, observed_at=EARLY)
            self.assertEqual(result["status"], "LOCAL_PRE")
            audit = audit_local_snapshots(root)
            self.assertEqual(audit["event_count"], 1)
            self.assertFalse(audit["externally_verified"])

    def test_reject_after_off(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "NO_PRE_WINDOW"):
                save_local_snapshot(root, FORECAST, observed_at=LATE)

    def test_reject_result_exposure(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "RESULT_EXPOSURE_NOT_EXCLUDED"):
                save_local_snapshot(root, dict(FORECAST, results_exposed=True), observed_at=EARLY)

    def test_reject_duplicate_object(self):
        with tempfile.TemporaryDirectory() as root:
            save_local_snapshot(root, FORECAST, observed_at=EARLY)
            with self.assertRaises(FileExistsError):
                save_local_snapshot(root, FORECAST, observed_at=EARLY)

    def test_reject_tampered_object(self):
        with tempfile.TemporaryDirectory() as root:
            receipt = save_local_snapshot(root, FORECAST, observed_at=EARLY)
            obj = Path(root) / "objects" / (receipt["forecast_sha256"] + ".json")
            obj.write_bytes(b"{}")
            with self.assertRaisesRegex(ValueError, "LOCAL_OBJECT_TAMPERED"):
                audit_local_snapshots(root)

    def test_reject_tampered_chain(self):
        with tempfile.TemporaryDirectory() as root:
            save_local_snapshot(root, FORECAST, observed_at=EARLY)
            path = Path(root) / "events" / "event-00000001.json"
            data = json.loads(path.read_bytes())
            data["previous_sha256"] = "f" * 64
            path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")))
            with self.assertRaisesRegex(ValueError, "AUDIT_CHAIN_BROKEN"):
                audit_local_snapshots(root)

if __name__ == "__main__":
    unittest.main()
