import tempfile
import unittest

from prism_ops.runtime import tick
from prism_ops.store import Store


class RuntimeConfigTests(unittest.TestCase):
    def test_invalid_config_is_rejected_before_acquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            try:
                for config in (None, {'jobs': {}}, {'watches': {}},
                               {'jobs': [None]}, {'watches': [{}]},
                               {'jobs': [{'race_id': '../outside'}]}):
                    with self.subTest(config=config), self.assertRaises(ValueError):
                        tick(config, store)
                self.assertEqual(store.jobs(), [])
            finally:
                store.close()

    def test_empty_jobs_do_not_claim_verified_universe(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            try:
                report = tick({'jobs': [], 'watches': []}, store)
                self.assertEqual(report['configured_races'], 0)
                self.assertFalse(report['official_race_universe_verified'])
                self.assertFalse(report['production_deployed'])
            finally:
                store.close()


if __name__ == '__main__':
    unittest.main()
