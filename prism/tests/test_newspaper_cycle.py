"""Publication acceptance tests; no official race data or API key required."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "run_newspaper_cycle.py"
spec = importlib.util.spec_from_file_location("run_newspaper_cycle", MODULE)
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class NewspaperPublicationGateTest(unittest.TestCase):
    def test_valid_real_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "page.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 20)
            (root / "paper.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 20)
            result = controller.check_publication(
                {"race_id": "R1", "png_files": ["page.png"], "pdf_file": "paper.pdf"},
                root, {"R1"},
            )
            self.assertEqual(result["race_id"], "R1")

    def test_missing_pdf_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "page.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 20)
            with self.assertRaises(ValueError):
                controller.check_publication(
                    {"race_id": "R1", "png_files": ["page.png"], "pdf_file": "missing.pdf"},
                    root, {"R1"},
                )

    def test_wrong_race_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                controller.check_publication(
                    {"race_id": "R2", "png_files": ["x.png"], "pdf_file": "x.pdf"},
                    Path(folder), {"R1"},
                )

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                controller.check_publication(
                    {"race_id": "R1", "png_files": ["../page.png"], "pdf_file": "paper.pdf"},
                    Path(folder), {"R1"},
                )


if __name__ == "__main__":
    unittest.main()
