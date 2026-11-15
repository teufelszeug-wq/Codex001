"""Synthetic fixture tests; no real publication, provider call or race outcome."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'src'), str(Path(__file__).resolve().parent)]
from prism_engine.contracts import digest
from prism_ops.daydelta import apply_day_delta, check_day_publication, publish_day_delta
from prism_ops.provider import OpenAIProvider, ProviderBlocked
from prism_ops.store import Store
from test_characters import snapshot_fixture

DAY = '2026-11-14T10:00:00+09:00'
PRE = '2026-11-13T20:00:00+09:00'
RACE = 'synthetic-day-race'
SOURCE = 'https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/DebaTable'


class DayDeltaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = PRE
        self.store = Store(self.temp.name, now=lambda: self.clock)
        self.addCleanup(self.store.close)
        self.snapshot = snapshot_fixture()
        self.author = self.snapshot['records'][0]['agent_id']
        race = {'race_id': RACE, 'race_name': 'SYNTHETIC RACE', 'authority': 'NAR',
                'start_at': '2026-11-14T15:00:00+09:00', 'required_forecasters': [self.author],
                'character_snapshot_hash': self.snapshot['snapshot_hash'],
                'source_refs': [SOURCE], 'runners': [
                    {'horse_id': 'h1', 'horse_no': 1, 'frame_no': 1, 'name': 'SYNTHETIC HORSE ONE'},
                    {'horse_id': 'h2', 'horse_no': 2, 'frame_no': 2, 'name': 'SYNTHETIC HORSE TWO'}]}
        # A fixture of the saved base contract; no software test certifies an
        # actual publication or independent execution by inserting these rows.
        self.bundle = {'schema': 'prism.ops.publication_bundle/v1', 'race': race,
                       'core_prediction': {'lock_hash': '0' * 64, 'win': {'h1': .6, 'h2': .4}},
                       'preliminary': {self.author: {'picks': []}}, 'discussions': [],
                       'final': {self.author: {'picks': [], 'content_hash': 'fixture-base'}}}
        self.store.save(RACE, 'characters', 'pre-v1', self.snapshot)
        self.base = self.store.save(RACE, 'bundle', 'pre-v1', self.bundle)
        self.publication = self.store.save(RACE, 'publication', 'pre-v1',
                     {'bundle_hash': self.base['content_hash'], 'published_at': PRE, 'gate': {'ready': True}})
        self.clock = DAY
        body = Path(self.temp.name) / 'synthetic-day-source.html'
        body.write_bytes(b'<html>SYNTHETIC source for day-delta software tests</html>')
        self.source = {'schema': 'prism.official_source_snapshot/v1', 'race_id': RACE,
                       'official_url': SOURCE, 'captured_at': DAY, 'source_sha256': sha256(body.read_bytes()).hexdigest(),
                       'body_path': str(body), 'mode': 'SYNTHETIC', 'identity_verified': False}
        self.calls = 0

        def transport(request, timeout):
            self.calls += 1
            context = json.loads(request['input'])['race_evidence']
            runners = context['runners']
            output = {'diagnoses': [{'horse_id': r['horse_id'], 'reason': 'SYNTHETIC day correction reason'} for r in runners],
                      'picks': [{'horse_id': runners[0]['horse_id'], 'mark': '◎', 'reason': 'SYNTHETIC reason'}],
                      'tickets': [], 'skip_reason': 'SYNTHETIC software test', 'change_reason': 'SYNTHETIC correction because supplied delta changed'}
            return {'id': 'synthetic-day-response-' + str(self.calls), 'status': 'completed',
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(output)}]}]}

        self.provider = OpenAIProvider(model='explicit-synthetic-model', transport=transport, now=lambda: self.clock)
        # Day-delta unit tests isolate their base fixture. The unpatched base
        # validator is tested separately and rejects this artificial record.
        self.base_check = patch('prism_ops.daydelta.check_publication', return_value={'ready': True, 'errors': []})
        self.base_check.start()
        self.addCleanup(self.base_check.stop)

    def apply(self, changes=None, **kwargs):
        return apply_day_delta(self.store, RACE, {'body_weight': {'h1': 480}} if changes is None else changes,
                               'SYNTHETIC observed body-weight update', self.source, self.provider,
                               now=lambda: self.clock, **kwargs)

    def test_day_candidate_preserves_base_and_core_and_is_resumable(self):
        first = self.apply()
        self.assertEqual(first['status'], 'SYNTHETIC_DAY_CANDIDATE')
        self.assertEqual(first['bundle']['core_prediction'], self.bundle['core_prediction'])
        self.assertEqual(self.store.get(RACE, 'bundle', 'pre-v1'), self.base)
        self.assertEqual(self.store.get(RACE, 'publication', 'pre-v1'), self.publication)
        self.assertIsNone(self.store.get(RACE, 'publication', 'day-v1'))
        self.assertEqual(self.calls, 1)
        second = self.apply()
        self.assertEqual(first['bundle'], second['bundle'])
        self.assertEqual(self.calls, 1)

    def test_no_changes_skip_without_provider(self):
        result = self.apply({})
        self.assertEqual(result['status'], 'SKIPPED_NO_CHANGES')
        self.assertEqual(self.calls, 0)

    def test_unknown_fields_and_nested_results_rejected(self):
        for changes in ({'ability': {'h1': 99}}, {'odds': {'results': {'winner': 1}}},
                        {'body_weight': {'unknown': 500}}, {'scratches': ['h1', 'h2']}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.apply(changes)
        self.assertEqual(self.calls, 0)

    def test_wrong_day_or_after_off_never_calls_provider(self):
        for value in ('2026-11-13T23:59:00+09:00', '2026-11-14T15:00:00+09:00', '2026-11-15T10:00:00+09:00'):
            self.clock = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.apply()
        self.assertEqual(self.calls, 0)

    def test_future_changed_or_wrong_race_source_rejected(self):
        original = deepcopy(self.source)
        for change in ({'captured_at': '2026-11-14T11:00:00+09:00'}, {'race_id': 'other-race'}, {'source_sha256': 'f' * 64}):
            self.source = dict(original, **change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.apply()
        self.assertEqual(self.calls, 0)

    def test_provider_failure_retains_candidate_but_no_completed_bundle(self):
        def timeout(body, timeout):
            raise TimeoutError()
        self.provider = OpenAIProvider(model='explicit-synthetic-model', transport=timeout, now=lambda: self.clock)
        with self.assertRaises(ProviderBlocked):
            self.apply()
        self.assertIsNotNone(self.store.get(RACE, 'day-delta', 'day-v1'))
        self.assertIsNone(self.store.get(RACE, 'bundle', 'day-v1'))
        self.assertEqual(self.store.jobs()[0]['status'], 'BLOCKED_DAY_CORRECTION')

    def test_deadline_crossing_retains_execution_but_never_completes_day_bundle(self):
        original_transport = self.provider._transport
        def late(request, timeout):
            response = original_transport(request, timeout)
            self.clock = '2026-11-14T15:01:00+09:00'
            return response
        self.provider._transport = late
        with self.assertRaisesRegex(ValueError, 'RACE_DAY_BEFORE_OFF'):
            self.apply()
        self.assertIsNotNone(self.store.get(RACE, 'executions', 'day-v1-final-' + self.author))
        self.assertIsNone(self.store.get(RACE, 'bundle', 'day-v1'))
        self.assertEqual(self.store.get(RACE, 'bundle', 'pre-v1'), self.base)

    def test_synthetic_cannot_publish_day_edition(self):
        self.apply()
        report = publish_day_delta(self.store, RACE, {}, now=lambda: self.clock)
        self.assertFalse(report['ready'])
        self.assertIsNone(self.store.get(RACE, 'publication', 'day-v1'))
        self.assertEqual(self.store.get(RACE, 'publication', 'pre-v1'), self.publication)
        again = check_day_publication(self.store, RACE, {}, published_at=self.clock,
                                     checked_at='2026-11-15T10:00:00+09:00')
        self.assertFalse(again['ready'])

    def test_scratches_keep_original_horses_only_in_base(self):
        result = self.apply({'scratches': ['h1']})
        self.assertEqual([r['horse_id'] for r in result['bundle']['race']['runners']], ['h2'])
        self.assertEqual(result['bundle']['race']['scratched_runners'][0]['horse_id'], 'h1')
        self.assertEqual(self.store.get(RACE, 'bundle', 'pre-v1')['payload']['race']['runners'], self.bundle['race']['runners'])

    def test_revisions_need_distinct_versions(self):
        self.apply()
        with self.assertRaises(ValueError):
            self.apply({'body_weight': {'h1': 482}})
        with self.assertRaises(ValueError):
            self.apply(version='pre-v1')
        revised = self.apply({'body_weight': {'h1': 482}}, version='day-v2')
        self.assertEqual(revised['bundle']['changes']['body_weight']['h1'], 482)

    def test_missing_formal_base_rejected(self):
        with self.assertRaises(ValueError):
            self.apply(base_edition='missing')
        self.assertEqual(self.calls, 0)

    def test_a_saved_ready_flag_cannot_substitute_for_valid_pre_day_evidence(self):
        self.base_check.stop()
        with self.assertRaisesRegex(ValueError, 'BASE_PUBLICATION_RECHECK_FAILED'):
            self.apply()
        self.assertEqual(self.calls, 0)

    def test_weight_and_rider_updates_change_only_day_race(self):
        result = self.apply({'body_weight': {'h1': 482}, 'body_weight_change': {'h1': -2},
                             'rider_change': {'h1': {'jockey_name': 'SYNTHETIC NEW RIDER', 'jockey_id': 'synthetic-rider'}},
                             'going': '稍重'})
        runner = result['bundle']['race']['runners'][0]
        self.assertEqual((runner['body_weight'], runner['body_weight_change'], runner['jockey_name']), (482, -2, 'SYNTHETIC NEW RIDER'))
        self.assertEqual(result['bundle']['race']['going'], '稍重')
        self.assertNotIn('body_weight', self.bundle['race']['runners'][0])

    def test_off_crossing_during_publication_save_is_not_success(self):
        self.apply()
        # Isolate fsync deadline behavior, rather than invent an independent
        # provider or a real paper approval in this software unit fixture.
        self.clock = '2026-11-14T15:01:00+09:00'
        with patch('prism_ops.daydelta.check_day_publication', return_value={
                'ready': True, 'errors': [], 'race_id': RACE, 'version': 'day-v1',
                'published_at': '2026-11-14T14:59:59+09:00', 'edition_kind': 'DAY_CORRECTION'}):
            report = publish_day_delta(self.store, RACE, {}, now=lambda: '2026-11-14T14:59:59+09:00')
        self.assertFalse(report['ready'])
        self.assertEqual(report['errors'], ['DAY_PUBLICATION_DURABLY_SAVED_AFTER_OFF'])
        self.assertEqual(self.store.jobs()[0]['status'], 'BLOCKED_DAY_PUBLICATION')


if __name__ == '__main__':
    unittest.main()
