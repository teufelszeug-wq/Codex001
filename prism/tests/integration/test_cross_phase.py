"""Synthetic cross-phase checks, not a real meeting or forward race."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT / 'tests/engine')]
from fixture import raw_fixture, market_fixture
from prism_engine import predict
from prism_engine.contracts import digest
from run_phase_abcde import build_release, write_release
from prism_dialogue import build_discussion_context
import importlib.util

spec = importlib.util.spec_from_file_location('dialogue_contract_fixture', ROOT / 'tests/dialogue/test_contracts.py')
dialogue_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dialogue_fixture)

WHEN = '2026-01-01T09:55:00+09:00'


class CrossPhase(unittest.TestCase):
    def setUp(self):
        self.raw = raw_fixture()
        self.market = market_fixture(predict(self.raw, WHEN))

    def test_same_input_deterministic_and_bound(self):
        a = build_release(self.raw, self.market, WHEN)
        self.assertEqual(a, build_release(self.raw, self.market, WHEN))
        p = a['pre_bundle.json']['prediction']
        for artifact in ('pre_manifest.json', 'discussion_context.json', 'release.json'):
            self.assertEqual(a[artifact]['race_id'], p['race_id'])
            self.assertEqual(a[artifact]['prediction_hash'], p['lock_hash'])
        self.assertEqual(a['discussion_audit.json']['status'], 'NOT_EXECUTED')
        self.assertFalse(a['release.json']['full_phase_abcde_complete'])
        self.assertIn('vertical-rl', a['paper.html'])

    def test_post_does_not_rewrite_pre(self):
        a = build_release(self.raw, self.market, WHEN)
        p = a['pre_bundle.json']['prediction']
        result = {'race_id': p['race_id'], 'prediction_hash': p['lock_hash'],
                  'available_at': '2026-01-01T10:05:00+09:00', 'refund_keys': [],
                  'complete_bet_types': sorted({c['bet_type'] for c in a['pre_bundle.json']['market_values']['candidate_values']}),
                  'payouts': []}
        b = build_release(self.raw, self.market, WHEN, result=result)
        for name, value in a.items():
            if name != 'release.json': self.assertEqual(value, b[name], name)
        self.assertEqual(b['pre_manifest.json']['pre_bundle_hash'], b['post_manifest.json']['pre_bundle_hash'])
        self.assertIn('settlement.json', b)

    def test_foreign_market_rejected(self):
        market = deepcopy(self.market); market['race_id'] = 'OTHER'
        with self.assertRaises(ValueError): build_release(self.raw, market, WHEN)

    def test_supplied_template_connects_but_never_becomes_training(self):
        pre = build_release(self.raw, self.market, WHEN)
        context = pre['discussion_context.json']
        records = dialogue_fixture.records_fixture(context)
        result = {'race_id': context['race_id'], 'prediction_hash': context['prediction_hash'],
                  'available_at': '2026-01-01T10:05:00+09:00', 'winners': ['h1']}
        result['content_hash'] = digest(result)
        release = build_release(self.raw, self.market, WHEN, discussion=records, learning_result=result)
        self.assertEqual(release['discussion_audit.json']['status'], 'STRUCTURAL_PASS')
        self.assertIn('テンプレート', release['paper.html'])
        self.assertEqual(release['discussion_audit.json']['counts']['verified_independent_sessions'], 0)
        self.assertFalse(release['learning_review.json']['model_parameters_changed'])
        self.assertEqual(release['pre_manifest.json']['artifacts']['paper'],
                         release['post_manifest.json']['artifacts']['paper'])

    def test_learning_without_discussion_rejected(self):
        with self.assertRaises(ValueError): build_release(self.raw, self.market, WHEN, learning_result={})

    def test_failed_discussion_does_not_publish(self):
        with self.assertRaises(ValueError): build_release(self.raw, self.market, WHEN, discussion={})

    def test_idempotent_write_and_preflight_conflict(self):
        release = build_release(self.raw, self.market, WHEN)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            first = write_release(path, release)
            self.assertEqual(first, write_release(path, release))
            other = deepcopy(release); other['paper.html'] += 'changed'
            other['new.json'] = {'must_not_write': True}
            with self.assertRaises(ValueError): write_release(path, other)
            self.assertFalse((path / 'new.json').exists())

    def test_changed_release_and_unsafe_names_cannot_be_written(self):
        release = build_release(self.raw, self.market, WHEN)
        with tempfile.TemporaryDirectory() as directory:
            changed = deepcopy(release); changed['paper.html'] += 'tamper'
            with self.assertRaises(ValueError): write_release(Path(directory)/'out', changed)
            self.assertFalse((Path(directory)/'out').exists())
            changed = deepcopy(release); changed['../escape.json'] = {}
            with self.assertRaises(ValueError): write_release(Path(directory)/'out', changed)
            self.assertFalse((Path(directory)/'escape.json').exists())

    def test_rehashed_paper_still_must_match_renderer(self):
        release = build_release(self.raw, self.market, WHEN)
        release['paper.html'] += 'tamper'
        report = release['release.json']
        report['artifacts'] = {k: digest(v) for k,v in release.items() if k != 'release.json'}
        report['release_hash'] = digest({k:v for k,v in report.items() if k != 'release_hash'})
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): write_release(Path(directory)/'out', release)
            self.assertFalse((Path(directory)/'out').exists())

    def test_self_rehash_cannot_forge_completion_or_identity(self):
        original = build_release(self.raw, self.market, WHEN)
        for key, value in [('race_id', 'OTHER'), ('execution_allowed', True),
                           ('full_phase_abcde_complete', True), ('discussion_status', 'REAL_MEETING')]:
            changed = deepcopy(original); report = changed['release.json']; report[key] = value
            report['release_hash'] = digest({k:v for k,v in report.items() if k != 'release_hash'})
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError): write_release(Path(directory)/'out', changed)
                self.assertFalse((Path(directory)/'out').exists())

    def test_cli_entrypoint_writes_verified_release(self):
        from prism_records import RecordStore
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'raw.json').write_text(json.dumps(self.raw), encoding='utf-8')
            (path / 'market.json').write_text(json.dumps(self.market), encoding='utf-8')
            db = path / 'records.sqlite'; store = RecordStore(db)
            store.add_race(self.raw['race']['race_id'], {'cutoff': self.raw['race']['cutoff']})
            for r in self.raw['runners']:
                hid = store.add_horse('SYNTHETIC:' + r['horse_id'], r['horse_id'])
                store.add_entry(self.raw['race']['race_id'], r['horse_no'], hid, frame_no=r['frame_no'])
            store.close()
            common = [sys.executable, str(ROOT / 'scripts/run_phase_abcde.py'),
                                     '--raw', str(path / 'raw.json'), '--market', str(path / 'market.json'),
                                     '--locked-at', WHEN]
            result = subprocess.run([*common, '--records-db', str(db), '--out', str(path / 'release')],
                                    capture_output=True, text=True, check=True)
            report = json.loads(result.stdout)
            self.assertFalse(report['execution_allowed'])
            self.assertEqual(report['discussion_status'], 'NOT_EXECUTED')
            self.assertTrue((path / 'release/paper.html').is_file())
            self.assertTrue((path / 'release/records_memory.json').is_file())
            replay = subprocess.run([*common, '--memory-file', str(path / 'release/records_memory.json'),
                                     '--out', str(path / 'replay')], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(replay.stdout)['release_hash'], report['release_hash'])

    def test_race_memo_is_frozen_once_without_changing_prediction(self):
        from prism_records import RecordStore
        from prism_records.memory import prepare_race_memory
        store = RecordStore(':memory:')
        try:
            store.add_race(self.raw['race']['race_id'], {'cutoff': self.raw['race']['cutoff']})
            store.add_race('TEST_PRIOR', {'cutoff': '2025-12-01T10:00:00+09:00'})
            for r in self.raw['runners']:
                hid = store.add_horse('SYNTHETIC:' + r['horse_id'], r['horse_id'])
                store.add_entry(self.raw['race']['race_id'], r['horse_no'], hid, frame_no=r['frame_no'])
                store.add_entry('TEST_PRIOR', r['horse_no'], hid, frame_no=r['frame_no'])
            memory = prepare_race_memory(store, self.raw['race']['race_id'], WHEN, ['RIO'])
        finally:
            store.close()
        plain = build_release(self.raw, self.market, WHEN)
        release = build_release(self.raw, self.market, WHEN, memory=memory)
        self.assertEqual(plain['pre_bundle.json']['prediction'], release['pre_bundle.json']['prediction'])
        self.assertEqual(release['records_memory.json'], memory)
        self.assertIn('records_memory', release['pre_manifest.json']['artifacts'])
        with tempfile.TemporaryDirectory() as directory:
            # Source DB is already closed: verification reuses the frozen memo.
            write_release(directory, release)

    def test_future_race_memo_cannot_enter_pre_context(self):
        from prism_records import RecordStore
        from prism_records.memory import prepare_race_memory
        store = RecordStore(':memory:')
        try:
            store.add_race(self.raw['race']['race_id'], {'cutoff': self.raw['race']['cutoff']})
            for r in self.raw['runners']:
                hid = store.add_horse('SYNTHETIC:' + r['horse_id'], r['horse_id'])
                store.add_entry(self.raw['race']['race_id'], r['horse_no'], hid, frame_no=r['frame_no'])
            memory = prepare_race_memory(store, self.raw['race']['race_id'],
                                         '2026-01-01T09:59:00+09:00', ['RIO'])
        finally:
            store.close()
        with self.assertRaises(ValueError): build_release(self.raw, self.market, WHEN, memory=memory)


if __name__ == '__main__': unittest.main()
