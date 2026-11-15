from pathlib import Path
import tempfile
import unittest

from prism_ops.store import Store
from prism_ops.reader import archive, paper_asset


class StoreTests(unittest.TestCase):
    def test_preserves_first_durable_receipt_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            try:
                first = store.save('race', 'bundle', 'pre-v1', {'prediction': 1})
                again = store.save('race', 'bundle', 'pre-v1', {'prediction': 1})
                self.assertEqual(first, again)
                with self.assertRaisesRegex(ValueError, 'IMMUTABLE'):
                    store.save('race', 'bundle', 'pre-v1', {'prediction': 2})
            finally:
                store.close()

    def test_artifact_tampering_and_unsafe_identity_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            try:
                saved = store.save('race', 'bundle', 'pre-v1', {'prediction': 1})
                Path(saved['path']).write_text('{"prediction":2}')
                with self.assertRaisesRegex(ValueError, 'INTEGRITY'):
                    store.get('race', 'bundle', 'pre-v1')
                with self.assertRaises(ValueError):
                    store.save('../outside', 'bundle', 'pre-v1', {})
            finally:
                store.close()

    def test_race_lock_prevents_concurrent_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            try:
                with store.lock('race'):
                    with self.assertRaisesRegex(RuntimeError, 'ALREADY_RUNNING'):
                        with store.lock('race'):
                            pass
            finally:
                store.close()

    def test_reader_escapes_untrusted_status_and_query(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            store.status('race', 'BLOCKED', {'reason': '<script>alert(1)</script>'})
            store.close()
            html = archive(directory, '')
            self.assertNotIn('<script>', html)
            self.assertIn('&lt;script&gt;', html)
            self.assertNotIn('<svg', archive(directory, '"><svg onload=alert(1)>'))


    def test_reader_paper_assets_stay_inside_private_paper_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            allowed = Path(directory) / 'papers' / 'race' / 'paper.pdf'
            self.assertEqual(paper_asset(directory, 'papers/race/paper.pdf'), allowed)
            for path in ('../private.pdf', 'artifacts/secret.json', 'papers/page.html'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    paper_asset(directory, path)


if __name__ == '__main__':
    unittest.main()
