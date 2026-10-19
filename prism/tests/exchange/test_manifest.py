"""Synthetic exchange-contract tests, not empirical Phase A completion."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import sys

from prism_engine.contracts import digest
from prism_exchange import build_manifest, verify_manifest, artifact_cache_key, write_manifest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import fixture as engine_fixture
from prism_engine.adapters import normalize
from prism_engine import post_market
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'dialogue'))
import test_contracts as dialogue_fixtures
from prism_dialogue import build_discussion_context, review_learning


class ExchangeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[2] / 'artifacts/audits/PHASE_B_SYNTHETIC_BUNDLE_20261018.json'
        cls.bundle = json.loads(path.read_text(encoding='utf-8'))

    def artifact(self, **overrides):
        payload = {'race_id': self.bundle['prediction']['race_id'],
                   'input_hash': self.bundle['prediction']['input_hash'],
                   'prediction_hash': self.bundle['prediction']['lock_hash'],
                   'mode': 'SYNTHETIC', 'result_revealed': False, 'text': '人工接続検証'}
        payload.update(overrides)
        return {'dialogue': {'stage': 'PRE', 'payload': payload}}

    def change_settlement(self, bundle):
        settlement = bundle['settlement']
        settlement['rows'][0]['payout_yen'] += 100
        settlement['rows'][0]['profit_yen'] += 100
        settlement['payout_yen'] += 100
        settlement['profit_yen'] += 100
        settlement['roi'] = settlement['payout_yen'] / settlement['effective_stake_yen']

    def test_deterministic_identity_and_no_certification(self):
        first = build_manifest(self.bundle, self.artifact())
        self.assertEqual(first, build_manifest(deepcopy(self.bundle), self.artifact()))
        self.assertTrue(verify_manifest(first, self.bundle, self.artifact()))
        self.assertEqual(first['race_id'], self.bundle['prediction']['race_id'])
        self.assertFalse(first['provenance']['strict_pit_certified'])
        self.assertFalse(first['provenance']['source_authenticity_verified'])
        self.assertFalse(first['execution_allowed'])

    def test_no_artifacts_and_artifact_order_are_deterministic(self):
        self.assertTrue(verify_manifest(build_manifest(self.bundle), self.bundle))
        artifacts = self.artifact()
        artifacts['paper'] = {'stage': 'PRE', 'payload': {'text': '紙面'}, 'depends_on': ['dialogue']}
        self.assertEqual(build_manifest(self.bundle, artifacts),
                         build_manifest(self.bundle, dict(reversed(list(artifacts.items())))))

    def test_manifest_change_rejected_even_if_rehashed(self):
        manifest = build_manifest(self.bundle)
        manifest['provenance']['strict_pit_certified'] = True
        manifest['manifest_hash'] = digest({k: v for k, v in manifest.items() if k != 'manifest_hash'})
        with self.assertRaises(ValueError):
            verify_manifest(manifest, self.bundle)

    def test_boolean_integer_substitution_is_tampering(self):
        manifest = build_manifest(self.bundle)
        manifest['execution_allowed'] = 0
        with self.assertRaises(ValueError):
            verify_manifest(manifest, self.bundle)

    def with_raw_and_card(self):
        bundle = deepcopy(self.bundle)
        bundle['raw'] = normalize(engine_fixture.observations_fixture())[0]
        bundle['racecard'] = [{'horse_id': r['horse_id'], 'horse_no': r['horse_no'],
                               'frame_no': r['frame_no'], 'name': '人工馬' + str(r['horse_no'])}
                              for r in bundle['raw']['runners']]
        return bundle

    def test_raw_hash_reverified_and_source_ref_not_certified(self):
        bundle = self.with_raw_and_card()
        manifest = build_manifest(bundle)
        self.assertTrue(manifest['provenance']['raw_input_payload_reverified'])
        self.assertEqual(manifest['provenance']['source_ref'], bundle['raw']['source'])
        self.assertFalse(manifest['provenance']['source_authenticity_verified'])
        bundle['raw']['runners'][0]['carried_weight'] = 60
        engine_fixture.seal(bundle['raw'])
        with self.assertRaisesRegex(ValueError, 'raw input hash mismatch'):
            build_manifest(bundle)

    def test_racecard_raw_binding_and_all_horse_coverage(self):
        for change in ('horse_no', 'frame_no', 'omit', 'duplicate', 'unknown'):
            bundle = self.with_raw_and_card()
            if change == 'horse_no':
                bundle['racecard'][0]['horse_no'] = 20
            elif change == 'frame_no':
                bundle['racecard'][0]['frame_no'] = 8
            elif change == 'omit':
                bundle['racecard'].pop()
            elif change == 'duplicate':
                bundle['racecard'].append(deepcopy(bundle['racecard'][0]))
            else:
                bundle['racecard'][0]['horse_id'] = 'unknown'
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_manifest(bundle)

    def test_rehashed_prediction_numbering_still_bound_to_raw(self):
        for horse, key, value in (('h1', 'horse_no', 7), ('h3', 'frame_no', 3), ('h1', 'barrier_no', 7)):
            bundle = self.with_raw_and_card()
            del bundle['settlement']
            prediction = bundle['prediction']
            prediction['features']['horses'][horse][key] = value
            if key == 'frame_no':
                prediction['frames'][horse] = str(value)
            prediction['lock_hash'] = digest({k: v for k, v in prediction.items() if k != 'lock_hash'})
            bundle['market_values'] = post_market(prediction, engine_fixture.market_fixture(prediction))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'raw/prediction'):
                build_manifest(bundle)

    def test_rehashed_plan_fixed_units_membership_and_content_rejected(self):
        for change in ('total', 'ticket_stake', 'duplicate', 'membership', 'content', 'candidate_arithmetic'):
            bundle = deepcopy(self.bundle)
            del bundle['settlement']
            plan = bundle['market_values']['plan']
            if change == 'total':
                plan['stake_yen'] = 1
            elif change == 'ticket_stake':
                plan['tickets'][0]['stake_yen'] = 1
            elif change == 'duplicate':
                plan['tickets'][1] = deepcopy(plan['tickets'][0])
            elif change == 'membership':
                key = plan['tickets'][0]['key']
                bundle['market_values']['candidate_values'] = [c for c in bundle['market_values']['candidate_values'] if c['key'] != key]
            elif change == 'content':
                plan['tickets'][0]['decimal_odds'] += 1
            else:
                bundle['market_values']['candidate_values'][0]['net_ev'] += 1
            plan['plan_hash'] = digest({k: v for k, v in plan.items() if k != 'plan_hash'})
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_manifest(bundle)

    def test_pre_cache_binds_racecard_names_and_raw_while_ignoring_settlement(self):
        bundle = self.with_raw_and_card()
        before = artifact_cache_key(bundle, 'paper', '紙面')
        self.change_settlement(bundle)
        self.assertEqual(before, artifact_cache_key(bundle, 'paper', '紙面'))
        bundle['racecard'][0]['name'] = '改名'
        self.assertNotEqual(before, artifact_cache_key(bundle, 'paper', '紙面'))

    def test_raw_result_leakage_rejected(self):
        bundle = self.with_raw_and_card()
        bundle['raw']['results'] = [{'horse_no': 1, 'rank': 1}]
        with self.assertRaises(ValueError):
            build_manifest(bundle)

    def test_unknown_bundle_and_nested_prediction_results_rejected(self):
        for key in ('result', 'results', 'official_result', 'unchecked'):
            bundle = deepcopy(self.bundle)
            bundle[key] = {'winner': 'h1'}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'unknown bundle'):
                build_manifest(bundle)
        bundle = deepcopy(self.bundle)
        bundle['prediction']['results'] = ['h1']
        bundle['prediction']['lock_hash'] = digest({k: v for k, v in bundle['prediction'].items() if k != 'lock_hash'})
        bundle['market_values']['prediction_hash'] = bundle['prediction']['lock_hash']
        bundle['market_values']['plan']['prediction_hash'] = bundle['prediction']['lock_hash']
        bundle['market_values']['plan']['plan_hash'] = digest({k: v for k, v in bundle['market_values']['plan'].items() if k != 'plan_hash'})
        with self.assertRaisesRegex(ValueError, 'result-bearing'):
            build_manifest(bundle)

    def test_dialogue_domain_stages_and_valid_learning_review(self):
        bundle = self.with_raw_and_card()
        pre = {k: v for k, v in bundle.items() if k != 'settlement'}
        context = build_discussion_context({k: v for k, v in pre.items() if k != 'racecard'})
        records = dialogue_fixtures.records_fixture(context)
        artifacts = {'discussion': {'stage': 'PRE', 'payload': records}}
        self.assertTrue(verify_manifest(build_manifest(pre, artifacts), pre, artifacts))
        result = {'race_id': context['race_id'], 'prediction_hash': context['prediction_hash'],
                  'available_at': '2026-01-01T11:00:00+09:00', 'winners': ['h1']}
        result['content_hash'] = digest(result)
        review = review_learning(context, records, result)
        bundle['learning_review'] = review
        self.assertTrue(verify_manifest(build_manifest(bundle, artifacts), bundle, artifacts))
        bundle['learning_review']['brier_sum'] += .1
        with self.assertRaisesRegex(ValueError, 'review hash'):
            build_manifest(bundle, artifacts)

    def test_post_settlement_arithmetic_and_ticket_binding_rejected(self):
        for change in ('total', 'row_profit', 'key', 'roi', 'unknown'):
            bundle = deepcopy(self.bundle)
            if change == 'total':
                bundle['settlement']['profit_yen'] += 1
            elif change == 'row_profit':
                bundle['settlement']['rows'][0]['profit_yen'] += 1
            elif change == 'key':
                bundle['settlement']['rows'][0]['key'] = 'not-the-plan'
            elif change == 'roi':
                bundle['settlement']['roi'] += .1
            else:
                bundle['settlement']['result'] = 'unchecked'
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_manifest(bundle)

    def test_prediction_change_rejected(self):
        bundle = deepcopy(self.bundle)
        bundle['prediction']['win']['h1'] = 0.9
        with self.assertRaisesRegex(ValueError, 'prediction lock changed'):
            build_manifest(bundle)

    def test_market_plan_and_normalization_mismatch_rejected(self):
        for section, key in [('market_values', 'prediction_hash'), ('normalization', 'normalized_hash')]:
            with self.subTest(section=section):
                bundle = deepcopy(self.bundle)
                bundle[section][key] = '0' * 64
                with self.assertRaises(ValueError):
                    build_manifest(bundle)
        bundle = deepcopy(self.bundle)
        bundle['market_values']['plan']['stake_yen'] += 100
        with self.assertRaisesRegex(ValueError, 'plan hash'):
            build_manifest(bundle)

    def test_artifact_binding_mismatch_rejected(self):
        for key in ('race_id', 'input_hash', 'prediction_hash', 'mode'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_manifest(self.bundle, self.artifact(**{key: 'not-this-race'}))

    def test_history_scope_requires_known_frozen_memory_schema(self):
        with self.assertRaisesRegex(ValueError, 'unknown race-memory schema'):
            build_manifest(self.bundle, {'memory': {'stage': 'PRE', 'payload': {
                'schema': 'prism.records.race-memory/v9',
                'race_id': self.bundle['prediction']['race_id']}}})
        with self.assertRaisesRegex(ValueError, 'race_id mismatch'):
            build_manifest(self.bundle, {'memory': {'stage': 'PRE', 'payload': {
                'schema': 'untrusted.history/v1', 'history': [{'race_id': 'PAST-RACE'}]}}})

    def frozen_memory(self, as_of=None):
        from prism_records import RecordStore
        from prism_records.memory import prepare_race_memory
        store = RecordStore(':memory:')
        try:
            horse = store.add_horse('test:memory-horse', '人工馬メモリー')
            store.add_race('PAST-RACE', {'cutoff': '2025-12-31T10:00:00+09:00'})
            store.add_entry('PAST-RACE', 1, horse, frame_no=1)
            store.add_observation(horse, 'PAST-RACE', {'phase': 'PRE', 'mode': 'SYNTHETIC', 'score': 1},
                                  'synthetic:prior-reference', '2025-12-31T09:00:00+09:00', 'PRE_AVAILABLE')
            race = self.bundle['prediction']['race_id']
            store.add_race(race, {'cutoff': self.bundle['prediction']['cutoff']})
            store.add_entry(race, 1, horse, frame_no=1)
            return prepare_race_memory(store, race, as_of or self.bundle['prediction']['locked_at'], ['RIO'])
        finally:
            store.close()

    def test_known_memory_snapshot_keeps_historical_identity_scope(self):
        snapshot = self.frozen_memory()
        self.assertIn('PAST-RACE', str(snapshot))
        artifact = {'memory': {'stage': 'PRE', 'payload': snapshot}}
        manifest = build_manifest(self.bundle, artifact)
        self.assertTrue(verify_manifest(manifest, self.bundle, artifact))
        self.assertFalse(manifest['provenance']['strict_pit_certified'])

    def test_memory_integrity_future_and_false_flag_guards(self):
        snapshot = self.frozen_memory()
        changed = deepcopy(snapshot)
        changed['as_of'] = '2026-01-01T09:56:00+09:00'
        # A valid independent snapshot may still be too late for this prediction.
        future = self.frozen_memory('2026-01-01T09:56:00+09:00')
        claimed = deepcopy(snapshot)
        claimed['source_authenticity_verified'] = True
        claimed['snapshot_hash'] = digest({k: v for k, v in claimed.items() if k != 'snapshot_hash'})
        wrong_race = deepcopy(snapshot)
        wrong_race['race_id'] = 'OTHER'
        wrong_race['snapshot_hash'] = digest({k: v for k, v in wrong_race.items() if k != 'snapshot_hash'})
        for value in (changed, future, claimed, wrong_race):
            with self.subTest(value=value['snapshot_hash']), self.assertRaises(ValueError):
                build_manifest(self.bundle, {'memory': {'stage': 'PRE', 'payload': value}})

    def test_future_lock_rejected_even_with_valid_hash(self):
        bundle = deepcopy(self.bundle)
        bundle['prediction']['locked_at'] = '2027-01-01T00:00:00Z'
        bundle['prediction']['lock_hash'] = digest({k: v for k, v in bundle['prediction'].items() if k != 'lock_hash'})
        with self.assertRaisesRegex(ValueError, 'after cutoff'):
            build_manifest(bundle)

    def test_missing_hash_bad_hash_and_nonfinite_rejected(self):
        for value in ('bad', None, 5):
            bundle = deepcopy(self.bundle)
            bundle['prediction']['input_hash'] = value
            with self.assertRaises(ValueError):
                build_manifest(bundle)
        with self.assertRaises(ValueError):
            build_manifest(self.bundle, {'x': {'stage': 'PRE', 'payload': float('nan')}})

    def test_pre_result_fields_rejected_recursively(self):
        for key in ('results', 'settlement', 'winners', 'payout_yen', 'profit_yen', 'outcome'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'result-bearing'):
                build_manifest(self.bundle, self.artifact(rows=[{key: [1]}]))
        with self.assertRaises(ValueError):
            build_manifest(self.bundle, self.artifact(result_revealed=True))

    def test_post_allowed_but_not_relabelled_pre(self):
        artifacts = {'review': {'stage': 'POST', 'payload': {'stage': 'POST', 'winners': ['h1']}}}
        manifest = build_manifest(self.bundle, artifacts)
        self.assertEqual(manifest['artifacts']['review']['stage'], 'POST')
        artifacts['review']['stage'] = 'PRE'
        with self.assertRaises(ValueError):
            build_manifest(self.bundle, artifacts)

    def test_payload_stage_conflict_rejected(self):
        with self.assertRaises(ValueError):
            build_manifest(self.bundle, self.artifact(stage='POST'))

    def test_dependencies_missing_self_duplicate_cycle_and_post_to_pre_rejected(self):
        graph_cases = [
            {'a': {'stage': 'PRE', 'payload': {}, 'depends_on': ['unknown']}},
            {'a': {'stage': 'PRE', 'payload': {}, 'depends_on': ['a']}},
            {'a': {'stage': 'PRE', 'payload': {}, 'depends_on': ['b', 'b']},
             'b': {'stage': 'PRE', 'payload': {}}},
            {'a': {'stage': 'POST', 'payload': {}, 'depends_on': ['b']},
             'b': {'stage': 'POST', 'payload': {}, 'depends_on': ['a']}},
            {'a': {'stage': 'PRE', 'payload': {}, 'depends_on': ['b']},
             'b': {'stage': 'POST', 'payload': {}}},
        ]
        for index, graph in enumerate(graph_cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                build_manifest(self.bundle, graph)

    def test_dependency_contents_invalidate_downstream_cache(self):
        artifacts = self.artifact()
        artifacts['paper'] = {'stage': 'PRE', 'payload': {}, 'depends_on': ['dialogue']}
        before = build_manifest(self.bundle, artifacts)
        artifacts['dialogue']['payload']['text'] = '新しい根拠'
        after = build_manifest(self.bundle, artifacts)
        self.assertNotEqual(before['artifacts']['paper']['cache_key'], after['artifacts']['paper']['cache_key'])

    def test_cache_key_changes_on_payload_but_not_post_settlement_for_pre(self):
        payload = self.artifact()['dialogue']['payload']
        before = artifact_cache_key(self.bundle, 'dialogue', payload)
        bundle = deepcopy(self.bundle)
        self.change_settlement(bundle)
        self.assertEqual(before, artifact_cache_key(bundle, 'dialogue', payload))
        self.assertNotEqual(build_manifest(self.bundle)['bundle_hash'], build_manifest(bundle)['bundle_hash'])
        self.assertNotEqual(before, artifact_cache_key(self.bundle, 'dialogue', {'text': '別'}))
        self.assertNotEqual(artifact_cache_key(self.bundle, 'review', {}, 'POST'),
                            artifact_cache_key(bundle, 'review', {}, 'POST'))

    def test_post_context_does_not_poison_pre_cache_through_dependency(self):
        graph = {'a': {'stage': 'PRE', 'payload': {}},
                 'b': {'stage': 'PRE', 'payload': {}, 'depends_on': ['a']}}
        before = build_manifest(self.bundle, graph)
        bundle = deepcopy(self.bundle)
        self.change_settlement(bundle)
        after = build_manifest(bundle, graph)
        self.assertEqual(before['artifacts'], after['artifacts'])

    def test_unsafe_kind_unknown_envelope_and_permission_rejected(self):
        for artifacts in ({'../a': {'stage': 'PRE', 'payload': {}}},
                          {'x': {'stage': 'PRE', 'payload': {}, 'unchecked': True}},
                          {'x': {'stage': 'UNKNOWN', 'payload': {}}}):
            with self.assertRaises(ValueError):
                build_manifest(self.bundle, artifacts)
        bundle = deepcopy(self.bundle)
        bundle['market_values']['execution_allowed'] = True
        with self.assertRaises(ValueError):
            build_manifest(bundle)

    def test_immutable_file_write_and_verify_before_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            manifest = build_manifest(self.bundle)
            self.assertEqual(write_manifest(path, manifest, self.bundle), manifest['manifest_hash'])
            self.assertEqual(write_manifest(path, manifest, self.bundle), manifest['manifest_hash'])
            changed = deepcopy(self.bundle)
            self.change_settlement(changed)
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                write_manifest(path, build_manifest(changed), changed)
            wrong_path = Path(directory) / 'new' / 'wrong.json'
            with self.assertRaises(ValueError):
                write_manifest(wrong_path, manifest, changed)
            self.assertFalse(wrong_path.exists())


if __name__ == '__main__':
    unittest.main()
