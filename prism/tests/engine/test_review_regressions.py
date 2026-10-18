from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from prism_engine import predict,DEFAULT_CONFIG
from prism_engine.market import settle,ticket_key
from prism_engine.contracts import digest
import test_engine as engine_fixtures
from fixture import raw_fixture,seal
LOCK='2026-01-01T09:55:00+09:00'

class ReviewRegressionTests(unittest.TestCase):
    def test_ability_recheck_orders_actual_instants(self):
        raw=raw_fixture();template=raw['runners'][0]['history'][0];rows=[]
        for stamp,score in [('2025-12-01T12:00:00+14:00',100),('2025-12-01T01:00:00Z',40),
                            ('2025-12-01T02:00:00Z',50),('2025-12-01T03:00:00Z',60)]:
            rows.append(dict(template,occurred_at=stamp,available_at='2025-12-02T00:00:00Z',performance_score=score))
        raw['runners'][0]['history']=rows;seal(raw)
        self.assertEqual(predict(raw,LOCK)['ability_rechecks']['h1']['recent_peak_score'],60)
    def test_known_post_lock_history_rejected_even_when_availability_unknown(self):
        raw=raw_fixture();raw['mode']='HISTORICAL_RECONSTRUCTION'
        raw['runners'][0]['history'][0]['occurred_at']='2026-01-01T09:59:00+09:00'
        raw['runners'][0]['history'][0]['available_at']=None;seal(raw)
        with self.assertRaisesRegex(ValueError,'history occurred after lock'):predict(raw,LOCK)
    def test_unsupported_extreme_temperature_rejected_at_configuration(self):
        config=deepcopy(DEFAULT_CONFIG);config['score_temperature']=.01
        with self.assertRaisesRegex(ValueError,'numeric range'):predict(raw_fixture(),LOCK,config)
    def test_precision_floor_never_equalizes_distinct_lower_rank_weights(self):
        from prism_engine.probability import softmax,marginals,distribution
        with self.assertRaisesRegex(ValueError,'too sharp'):softmax({'a':100.,'b':90.,'c':0.},.01)
        p=softmax({'a':100.,'b':90.,'c':0.},1.)
        joint=marginals(p,distribution(p));self.assertGreater(joint['top2']['b'],.999)
        self.assertLess(joint['top2']['c'],.001)
    def test_withdrawal_does_not_rebase_other_barriers(self):
        raw=raw_fixture();a=predict(raw,LOCK);raw['runners'].pop()
        raw['specialists']=[s for s in raw['specialists'] if s['horse_id']!='h6'];seal(raw);b=predict(raw,LOCK)
        self.assertEqual(a['features']['horses']['h5']['components']['bias_tbi_ssi'],b['features']['horses']['h5']['components']['bias_tbi_ssi'])
    def test_barrier_is_not_horse_or_frame_number(self):
        raw=raw_fixture();a=predict(raw,LOCK)
        raw['runners'][0]['horse_no'],raw['runners'][1]['horse_no']=2,1;seal(raw)
        b=predict(raw,LOCK)
        self.assertEqual(a['features']['horses']['h1']['components']['bias_tbi_ssi'],b['features']['horses']['h1']['components']['bias_tbi_ssi'])
    def test_duplicate_tickets_rejected_even_with_consistent_plan_hash(self):
        fixture=engine_fixtures.SettlementTests();p=fixture.plan();p['tickets']*=2;p['stake_yen']=200;p['plan_hash']=digest({k:v for k,v in p.items() if k!='plan_hash'})
        with self.assertRaisesRegex(ValueError,'duplicate tickets'):settle(p,fixture.result(),'r','2026-01-01T10:00:00Z')
    def test_wrong_prediction_settlement_rejected(self):
        fixture=engine_fixtures.SettlementTests();r=fixture.result();r['prediction_hash']='other'
        with self.assertRaisesRegex(ValueError,'binding'):settle(fixture.plan(),r,'r','2026-01-01T10:00:00Z')
    def test_wrong_plan_total_rejected(self):
        fixture=engine_fixtures.SettlementTests();p=fixture.plan();p['stake_yen']=1000;p['plan_hash']=digest({k:v for k,v in p.items() if k!='plan_hash'})
        with self.assertRaisesRegex(ValueError,'total'):settle(p,fixture.result(),'r','2026-01-01T10:00:00Z')
