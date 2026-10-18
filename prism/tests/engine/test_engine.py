from copy import deepcopy
from itertools import permutations
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from prism_engine import predict,post_market,DEFAULT_CONFIG
from prism_engine.contracts import digest,validate
from prism_engine.probability import distribution,marginals,simulate,fit_calibration
from prism_engine.market import value_candidates,ticket_key,settle,optimize,hit
from fixture import raw_fixture,seal,calibration_fixture,market_fixture

LOCK='2026-01-01T09:55:00+09:00'

class InputTests(unittest.TestCase):
    def test_sealed_input_unchanged(self):
        raw=raw_fixture();before=deepcopy(raw);predict(raw,LOCK);self.assertEqual(raw,before)
    def test_unknown_top_fields_fail(self):
        for key in ('results','win_payouts','odds','market','future_extension'):
            raw=raw_fixture();raw[key]={};seal(raw)
            with self.subTest(key=key),self.assertRaises(ValueError):predict(raw,LOCK)
    def test_nested_unrecognized_fields_fail(self):
        for key in ('results','odds','finish_position'):
            raw=raw_fixture();raw['runners'][0]['state'][key]=1;seal(raw)
            with self.subTest(key=key),self.assertRaises(ValueError):predict(raw,LOCK)
    def test_hash_tamper_fail(self):
        raw=raw_fixture();raw['runners'][0]['carried_weight']=56
        with self.assertRaises(ValueError):predict(raw,LOCK)
    def test_duplicate_horse_number(self):
        raw=raw_fixture();raw['runners'][1]['horse_no']=1;seal(raw)
        with self.assertRaises(ValueError):predict(raw,LOCK)
    def test_duplicate_identity(self):
        raw=raw_fixture();raw['runners'][1]['horse_id']='h1';seal(raw)
        with self.assertRaises(ValueError):predict(raw,LOCK)
    def test_shared_frame_is_valid(self):
        lock=predict(raw_fixture(),LOCK);self.assertEqual(lock['frames']['h1'],lock['frames']['h2'])
    def test_zero_style_rejected(self):
        raw=raw_fixture()
        for k in ('escape','front','mid','closer'):raw['runners'][0]['style'][k]=0
        seal(raw)
        with self.assertRaises(ValueError):predict(raw,LOCK)
    def test_nonfinite_and_bool_rejected(self):
        for value in (float('nan'),float('inf'),True):
            raw=raw_fixture();raw['runners'][0]['carried_weight']=value
            with self.subTest(value=value),self.assertRaises(ValueError):seal(raw);predict(raw,LOCK)
    def test_current_or_future_history_rejected(self):
        raw=raw_fixture();raw['runners'][0]['history'][0]['occurred_at']='2026-01-01T10:00:00+09:00';seal(raw)
        with self.assertRaises(ValueError):predict(raw,LOCK)
    def test_future_features_rejected(self):
        raw=raw_fixture();raw['runners'][0]['workout']['available_at']='2026-01-02T09:00:00+09:00';seal(raw)
        with self.assertRaises(ValueError):predict(raw,LOCK)
    def test_feature_after_lock_before_cutoff_rejected(self):
        raw=raw_fixture();raw['runners'][0]['workout']['available_at']='2026-01-01T09:56:00+09:00';seal(raw)
        with self.assertRaises(ValueError):predict(raw,LOCK)
    def test_unknown_times_reconstruction_only(self):
        raw=raw_fixture();raw['source']['available_at']=None
        with self.assertRaises(ValueError):predict(raw,LOCK)
        raw['mode']='HISTORICAL_RECONSTRUCTION';seal(raw);self.assertEqual(predict(raw,LOCK)['mode'],'HISTORICAL_RECONSTRUCTION')
    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):predict(raw_fixture(),'2026-01-01T09:55:00')
    def test_late_prediction_lock_rejected(self):
        with self.assertRaises(ValueError):predict(raw_fixture(),'2026-01-01T10:01:00+09:00')
    def test_cold_prior_explicit(self):
        raw=raw_fixture();raw['runners'][0]['history']=[];seal(raw);lock=predict(raw,LOCK)
        self.assertEqual(lock['coverage']['h1']['base_ability'],'EXPLICIT_PRIOR')
        self.assertIsNone(lock['features']['horses']['h1']['components']['course_surface_class'])
    def test_missing_feature_retained(self):
        raw=raw_fixture();del raw['runners'][0]['workout'];seal(raw);lock=predict(raw,LOCK)
        self.assertEqual(lock['coverage']['h1']['workout'],'UNAVAILABLE')
    def test_bias_sign_equivalence(self):
        raw=raw_fixture();a=predict(raw,LOCK);raw['bias']['positive_lane']='INNER'
        raw['bias']['gate']*=-1;raw['bias']['path']*=-1;seal(raw)
        self.assertEqual(a['scores'],predict(raw,LOCK)['scores'])
    def test_banei_not_flat_pace(self):
        lock=predict(raw_fixture('BANEI'),LOCK);self.assertIsNone(lock['features']['pace_distribution'])
        self.assertEqual(lock['coverage']['h1']['sectional'],'UNAVAILABLE')
        self.assertIsNotNone(lock['features']['horses']['h1']['components']['surface_specific'])
    def test_jump_route(self):
        lock=predict(raw_fixture('JUMP'),LOCK);self.assertIsNone(lock['features']['pace_distribution'])
        self.assertNotEqual(lock['features']['horses']['h1']['components']['surface_specific'],0)
    def test_shared_specialist_evidence_not_counted_twice(self):
        raw=raw_fixture();first=predict(raw,LOCK);x=deepcopy(raw['specialists'][0]);x['agent_id']='SECOND';raw['specialists'].append(x);seal(raw)
        self.assertEqual(first['scores'],predict(raw,LOCK)['scores'])
    def test_disabled_component_removes_effect(self):
        lock=predict(raw_fixture(),LOCK,disabled_modules=['workout']);self.assertEqual(lock['coverage']['h1']['workout'],'DISABLED')
        self.assertNotEqual(lock['scores'],predict(raw_fixture(),LOCK)['scores'])

class ProbabilityTests(unittest.TestCase):
    def test_exact_distribution_against_uniform(self):
        win={f'h{i}':.25 for i in range(4)};rows=distribution(win);p=marginals(win,rows)
        self.assertAlmostEqual(sum(v for _,v in rows),1)
        self.assertTrue(all(abs(p['top2'][k]-.5)<1e-9 for k in win))
        self.assertTrue(all(abs(p['top3'][k]-.75)<1e-9 for k in win))
    def test_two_runner_probabilities(self):
        win={'h1':.6,'h2':.4};p=marginals(win,distribution(win));self.assertEqual(p['top2'],{'h1':1.,'h2':1.})
    def test_monte_carlo_repeatable_and_close(self):
        win={'h1':.6,'h2':.4};a=simulate(win,20000,99)
        self.assertEqual(a,simulate(win,20000,99));self.assertLess(abs(a['win']['h1']-.6),.02)
        self.assertEqual(a['top2'],{'h1':1.,'h2':1.});self.assertEqual(a['top3'],{'h1':1.,'h2':1.})
    def test_monte_carlo_joint_marginals(self):
        win={f'h{i}':.25 for i in range(4)};a=simulate(win,20000,12)
        self.assertAlmostEqual(sum(a['top2'].values()),2);self.assertAlmostEqual(sum(a['top3'].values()),3)
        self.assertTrue(all(abs(a['top3'][k]-.75)<.02 for k in win))
    def test_pipeline_repeatable(self):
        self.assertEqual(predict(raw_fixture(),LOCK,calibration=calibration_fixture()),predict(raw_fixture(),LOCK,calibration=calibration_fixture()))
    def test_calibration_no_target_leakage(self):
        c=calibration_fixture();c['training_race_ids'].append(raw_fixture()['race']['race_id']);c['artifact_hash']=digest({k:v for k,v in c.items() if k!='artifact_hash'})
        with self.assertRaises(ValueError):predict(raw_fixture(),LOCK,calibration=c)
    def test_calibration_after_lock_rejected(self):
        c=calibration_fixture();c['trained_until']='2026-01-01T09:59:00+09:00';c['artifact_hash']=digest({k:v for k,v in c.items() if k!='artifact_hash'})
        with self.assertRaises(ValueError):predict(raw_fixture(),LOCK,calibration=c)
    def test_calibration_artifact_tamper_rejected(self):
        c=calibration_fixture();c['temperature']=10
        with self.assertRaises(ValueError):predict(raw_fixture(),LOCK,calibration=c)
    def test_calibration_unknown_result_time_rejected(self):
        rows=[{'race_id':'x','outcome_available_at':'2026-01-02T01:00:00Z','probabilities':{'a':1},'winners':['a']}]
        with self.assertRaises(ValueError):fit_calibration(rows,'2026-01-01T01:00:00Z',[1])
    def test_identity_calibration_not_claimed_fitted(self):
        self.assertEqual(predict(raw_fixture(),LOCK)['calibration_status'],'IDENTITY_NOT_FITTED')

class MarketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lock=predict(raw_fixture(),LOCK,calibration=calibration_fixture())
    def test_all_eight_ticket_types(self):
        values=value_candidates(self.lock,market_fixture(self.lock),DEFAULT_CONFIG)
        self.assertEqual({x['bet_type'] for x in values},{'WIN','PLACE','QUINELLA','EXACTA','WIDE','TRIO','TRIFECTA','FRAME'})
        for v in values:
            self.assertAlmostEqual(v['net_ev'],v['probability']*v['decimal_odds']-1)
            self.assertTrue(0<=v['probability']<=1)
    def test_nvalue_recheck_is_separate_from_main_probability(self):
        before=deepcopy(self.lock['win']);out=post_market(self.lock,market_fixture(self.lock))
        self.assertEqual(len(out['nvalue_reviews']),6);self.assertEqual(self.lock['win'],before)
        self.assertTrue(all(not r['automatic_adoption'] for r in out['nvalue_reviews']))
    def test_pace_scenarios_expose_distinct_probabilities(self):
        scenarios=self.lock['scenario_win_uncalibrated'];self.assertEqual(len(scenarios),5)
        self.assertNotEqual(scenarios['VERY_HIGH'],scenarios['VERY_SLOW'])
    def test_same_frame_probability_not_same_horse(self):
        v=next(x for x in value_candidates(self.lock,market_fixture(self.lock),DEFAULT_CONFIG) if x['bet_type']=='FRAME')
        p=sum(p for order,p in self.lock['rank_distribution'] if set(order[:2])=={'h1','h2'})
        self.assertAlmostEqual(v['probability'],p)
    def test_value_uses_lower_range(self):
        values=value_candidates(self.lock,market_fixture(self.lock),DEFAULT_CONFIG)
        self.assertEqual(next(x for x in values if x['bet_type']=='WIDE')['decimal_odds'],20)
    def test_market_change_cannot_change_prediction(self):
        before=deepcopy(self.lock);m=market_fixture(self.lock);post_market(self.lock,m)
        m['quotes'][0]['odds_low']=1;m['quotes'][0]['odds_high']=1;post_market(self.lock,m)
        self.assertEqual(before,self.lock)
    def test_quote_before_lock_access_rejected(self):
        m=market_fixture(self.lock);m['opened_at']='2026-01-01T09:54:00+09:00';m['observed_at']=m['opened_at']
        with self.assertRaises(ValueError):post_market(self.lock,m)
    def test_stale_quote_rejected(self):
        m=market_fixture(self.lock);m['observed_at']='2026-01-01T09:00:00+09:00'
        with self.assertRaises(ValueError):post_market(self.lock,m)
    def test_lock_tamper_rejected(self):
        lock=deepcopy(self.lock);lock['win']['h1']=.5
        with self.assertRaises(ValueError):post_market(lock,market_fixture(lock))
    def test_market_wrong_prediction_rejected(self):
        m=market_fixture(self.lock);m['prediction_hash']='0'*64
        with self.assertRaises(ValueError):post_market(self.lock,m)
    def test_config_change_after_lock_rejected(self):
        c=deepcopy(DEFAULT_CONFIG);c['budget_yen']=100
        with self.assertRaises(ValueError):post_market(self.lock,market_fixture(self.lock),c)
    def test_duplicate_quote_rejected(self):
        m=market_fixture(self.lock);m['quotes'].append(deepcopy(m['quotes'][0]))
        with self.assertRaises(ValueError):post_market(self.lock,m)
    def test_no_bet_without_edge(self):
        m=market_fixture(self.lock)
        for q in m['quotes']:q['odds_low']=q['odds_high']=1
        self.assertEqual(post_market(self.lock,m)['plan']['decision'],'NO_BET')
    def test_fixed_stake_budget_and_exposure(self):
        plan=post_market(self.lock,market_fixture(self.lock))['plan']
        self.assertLessEqual(plan['stake_yen'],500);self.assertTrue(all(t['stake_yen']==100 for t in plan['tickets']))
    def test_exact_optimizer_beats_greedy_exposure(self):
        c=deepcopy(DEFAULT_CONFIG);c['max_exposure_per_leg']=1
        def item(key,legs,gain):return {'key':key,'legs':legs,'bet_type':'QUINELLA','net_ev':gain/100,'expected_profit_yen':gain,'stake_yen':100}
        result=optimize([item('a',['a','b'],10),item('b',['a','c'],6),item('c',['b','d'],6)],c)
        self.assertEqual(result['expected_profit_yen'],12)
    def test_ordered_and_unordered_keys(self):
        self.assertEqual(ticket_key('QUINELLA',['a','b']),ticket_key('QUINELLA',['b','a']))
        self.assertNotEqual(ticket_key('EXACTA',['a','b']),ticket_key('EXACTA',['b','a']))
    def test_impossible_same_frame_rejected(self):
        m=market_fixture(self.lock);m['quotes']=[{'bet_type':'FRAME','legs':['2','2'],'odds_low':2,'odds_high':2}]
        with self.assertRaises(ValueError):post_market(self.lock,m)
    def test_result_not_accepted_as_market(self):
        m=market_fixture(self.lock);m['payouts']=[]
        with self.assertRaises(ValueError):post_market(self.lock,m)

class SettlementTests(unittest.TestCase):
    def plan(self):
        plan={'race_id':'r','prediction_hash':'synthetic-prediction','stake_yen':100,
              'tickets':[{'key':ticket_key('WIN',['h1']),'bet_type':'WIN','legs':['h1'],'stake_yen':100}]}
        plan['plan_hash']=digest(plan);return plan
    def result(self):
        return {'race_id':'r','prediction_hash':'synthetic-prediction','available_at':'2026-01-01T11:00:00Z','payouts':[{'bet_type':'WIN','legs':['h1'],'payout_per_100_yen':350}],
                'refund_keys':[],'complete_bet_types':['WIN']}
    def test_win_fixed100(self):
        r=settle(self.plan(),self.result(),'r','2026-01-01T10:00:00Z');self.assertEqual(r['profit_yen'],250);self.assertEqual(r['roi'],3.5)
    def test_refund_excluded_from_roi(self):
        p=self.plan();r=self.result();r['payouts']=[];r['refund_keys']=[p['tickets'][0]['key']]
        x=settle(p,r,'r','2026-01-01T10:00:00Z');self.assertIsNone(x['roi']);self.assertEqual(x['profit_yen'],0)
    def test_official_dead_heat_payout_is_used(self):
        r=self.result();r['payouts'][0]['payout_per_100_yen']=170
        self.assertEqual(settle(self.plan(),r,'r','2026-01-01T10:00:00Z')['profit_yen'],70)
    def test_incomplete_result_not_silent_loss(self):
        r=self.result();r['complete_bet_types']=[]
        with self.assertRaises(ValueError):settle(self.plan(),r,'r','2026-01-01T10:00:00Z')
    def test_wrong_race_rejected(self):
        with self.assertRaises(ValueError):settle(self.plan(),self.result(),'wrong','2026-01-01T10:00:00Z')
    def test_non100_stake_rejected(self):
        p=self.plan();p['tickets'][0]['stake_yen']=200
        with self.assertRaises(ValueError):settle(p,self.result(),'r','2026-01-01T10:00:00Z')
    def test_refund_payout_conflict_rejected(self):
        r=self.result();r['refund_keys']=[self.plan()['tickets'][0]['key']]
        with self.assertRaises(ValueError):settle(self.plan(),r,'r','2026-01-01T10:00:00Z')

if __name__=='__main__':unittest.main()
