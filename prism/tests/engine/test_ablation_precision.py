"""Engineering ablations are component removals, not trained causal estimates."""
from copy import deepcopy
from math import log
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from prism_engine import predict,post_market,DEFAULT_CONFIG
from prism_engine.contracts import digest
from prism_engine.engine import MODULES
from prism_engine.market import ticket_key
from prism_engine.probability import apply_calibration,fit_calibration
from fixture import raw_fixture,seal,calibration_fixture,market_fixture

LOCK='2026-01-01T09:55:00+09:00'


class AblationAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=deepcopy(DEFAULT_CONFIG);cls.config['runs']=100
        cls.raw=raw_fixture();cls.baseline=predict(cls.raw,LOCK,cls.config)

    def test_every_module_removal_has_exact_score_accounting(self):
        for module in MODULES:
            with self.subTest(module=module):
                lock=predict(self.raw,LOCK,self.config,disabled_modules=[module])
                self.assertEqual(lock['ablation']['disabled_modules'],[module])
                self.assertNotIn(module,lock['ablation']['enabled_modules'])
                for horse,feature in self.baseline['features']['horses'].items():
                    removed=feature['base_ability']-self.config['cold_start_prior'] if module=='base_ability' else feature['components'][module] or 0.
                    self.assertAlmostEqual(lock['scores'][horse],self.baseline['scores'][horse]-removed)
                    self.assertEqual(lock['coverage'][horse][module],'DISABLED')

    def test_effective_contributions_reconstruct_every_locked_score(self):
        for horse,components in self.baseline['ablation']['effective_components'].items():
            self.assertAlmostEqual(sum(components.values()),self.baseline['scores'][horse],places=12)
        self.assertEqual(self.baseline['ablation']['score_reconstruction_hash'],digest(self.baseline['ablation']['effective_components']))

    def test_all_components_disabled_yields_explicit_uniform_prior(self):
        lock=predict(self.raw,LOCK,self.config,disabled_modules=MODULES)
        self.assertTrue(all(score==self.config['cold_start_prior'] for score in lock['scores'].values()))
        self.assertTrue(all(abs(p-1/6)<1e-12 for p in lock['win'].values()))
        self.assertEqual(lock['ablation']['enabled_modules'],[])
        self.assertFalse(lock['ablation']['scenario_scores_include_pace_replacement'])

    def test_disabled_pace_removes_joint_scenario_mixture(self):
        lock=predict(self.raw,LOCK,self.config,disabled_modules=['pace'])
        self.assertEqual(set(lock['scenario_win_uncalibrated']),{'NO_PACE_MODEL'})
        self.assertIsNotNone(lock['features']['pace_distribution'])
        self.assertTrue(lock['ablation']['diagnostic_features_retained'])

    def test_disabled_workout_input_cannot_change_scores_or_probabilities(self):
        changed=deepcopy(self.raw);changed['runners'][0]['workout']['score']=0;seal(changed)
        a=predict(self.raw,LOCK,self.config,disabled_modules=['workout'])
        b=predict(changed,LOCK,self.config,disabled_modules=['workout'])
        self.assertEqual(a['scores'],b['scores']);self.assertEqual(a['win'],b['win'])
        self.assertNotEqual(a['input_hash'],b['input_hash'])

    def test_unavailable_component_does_not_become_observed_zero(self):
        raw=deepcopy(self.raw);del raw['runners'][0]['workout'];seal(raw)
        lock=predict(raw,LOCK,self.config)
        self.assertEqual(lock['coverage']['h1']['workout'],'UNAVAILABLE')
        self.assertIsNone(lock['features']['horses']['h1']['components']['workout'])
        self.assertEqual(lock['ablation']['effective_components']['h1']['workout'],0)

    def test_banei_surface_component_is_actually_removed(self):
        raw=raw_fixture('BANEI');base=predict(raw,LOCK,self.config)
        lock=predict(raw,LOCK,self.config,disabled_modules=['surface_specific'])
        for horse in base['scores']:
            self.assertAlmostEqual(base['scores'][horse]-lock['scores'][horse],base['features']['horses'][horse]['components']['surface_specific'])

    def test_ablation_order_and_duplicates_do_not_change_lock(self):
        a=predict(self.raw,LOCK,self.config,disabled_modules=['pace','workout'])
        b=predict(self.raw,LOCK,self.config,disabled_modules=['workout','pace','pace'])
        self.assertEqual(a,b)

    def test_post_market_retains_validated_observation_and_access_times(self):
        market=market_fixture(self.baseline)
        market['opened_at']='2026-01-01T09:57:00+09:00'
        result=post_market(self.baseline,market,self.config)
        self.assertEqual(result['observed_at'],market['observed_at'])
        self.assertEqual(result['opened_at'],market['opened_at'])
        self.assertTrue(result['timestamps_are_declared_not_attested'])

    def test_post_market_time_fields_do_not_rewrite_prediction_cutoff(self):
        before=deepcopy(self.baseline);market=market_fixture(self.baseline)
        result=post_market(self.baseline,market,self.config)
        self.assertNotEqual(result['opened_at'],self.baseline['cutoff'])
        self.assertEqual(self.baseline,before)


class CalibrationPrecisionTests(unittest.TestCase):
    def identity_artifact(self):
        artifact=calibration_fixture();artifact['temperature']=1.
        artifact['artifact_hash']=digest({k:v for k,v in artifact.items() if k!='artifact_hash'})
        return artifact

    def test_identity_calibration_preserves_distinct_sub_floor_tails(self):
        win={'a':1-1e-13,'b':9e-14,'c':1e-14}
        result,_=apply_calibration(win,self.identity_artifact(),'TARGET',LOCK)
        self.assertAlmostEqual(result['b']/result['c'],9,places=10)
        for horse in win:self.assertAlmostEqual(result[horse]/win[horse],1,places=12)

    def test_fit_uses_actual_small_probability_log_loss(self):
        row={'race_id':'TRAIN','outcome_available_at':'2025-01-01T00:00:00Z',
             'probabilities':{'a':1-1e-14,'b':1e-14},'winners':['b']}
        artifact=fit_calibration([row],'2025-01-02T00:00:00Z',[1.])
        self.assertAlmostEqual(artifact['training_log_loss'],-log(1e-14),places=10)

    def test_zero_probability_training_is_explicitly_unsupported(self):
        row={'race_id':'TRAIN','outcome_available_at':'2025-01-01T00:00:00Z',
             'probabilities':{'a':1.,'b':0.},'winners':['a']}
        with self.assertRaisesRegex(ValueError,'strictly positive'):
            fit_calibration([row],'2025-01-02T00:00:00Z',[1.])

    def test_zero_probability_application_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(ValueError,'strictly positive'):
            apply_calibration({'a':1.,'b':0.},self.identity_artifact(),'TARGET',LOCK)

    def test_ticket_legs_must_be_a_sequence_not_a_string(self):
        with self.assertRaisesRegex(ValueError,'ticket shape'):ticket_key('WIN','a')


if __name__=='__main__':unittest.main()
