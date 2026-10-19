import copy
import unittest
from prism_validation.feature_replay import build_rows, settle, bootstrap_deltas, model_input


def race(key,date,winner=1):
    return {'race_id':key,'date':date,'start':'1000','surface':'DIRT',
            'entrants':[{'number':1,'identity':'a'},{'number':2,'identity':'b'}],
            'results':[{'number':n,'rank':1 if n==winner else 2,'status':str(1 if n==winner else 2)} for n in (1,2)],
            'win_payouts':{str(winner):200}}


class FeatureReplayTests(unittest.TestCase):
    def test_same_day_results_cannot_change_features_or_baseline(self):
        races = [race('r1','20260101'),race('r2','20260101'),race('r3','20260102')]
        obs = {(r['race_id'],str(n)):{'jockey_id':str(n),'body_weight':450,'body_change':0} for r in races for n in (1,2)}
        before = build_rows(races,[],obs)
        races[0]['results'] = race('r1','20260101',2)['results']
        after = build_rows(races,[],obs)
        self.assertEqual(model_input(before[1]),model_input(after[1]))
        self.assertNotEqual(before[2]['features'],after[2]['features'])
        self.assertIsNone(before[0]['features']['1']['jockey_signal'])

    def test_missing_weight_differs_from_zero_change(self):
        rows = build_rows([race('r','20260101')],[],{('r','1'):{'body_weight':450,'body_change':0}})
        self.assertEqual(rows[0]['features']['1']['body_change'],0)
        self.assertIsNone(rows[0]['features']['2']['body_change'])

    def test_winning_missing_payout_is_not_zero(self):
        r = race('r','20260101');r['win_payouts'] = {}
        with self.assertRaisesRegex(ValueError,'payout unavailable'):settle({'1':.8,'2':.2},r)
        self.assertEqual(settle({'1':.2,'2':.8},r)['payout_excluding_refund_yen'],0)

    def test_refund_and_dead_heat(self):
        r = race('r','20260101');r['results'][1]['status']='取消'
        self.assertEqual(settle({'1':.1,'2':.9},r)['refund_yen'],100)
        r['results'][1].update(status='1',rank=1);r['win_payouts']['2']=150
        row=settle({'1':.1,'2':.9},r)
        self.assertEqual(row['payout_excluding_refund_yen'],150)
        self.assertEqual(len(row['winners']),2)

    def test_bootstrap_paired_and_repeatable(self):
        rows=[settle({'1':.5,'2':.5},race(str(i),'2026010'+str(i))) for i in (1,2)]
        self.assertEqual(bootstrap_deltas(rows,rows,50)['interval_95']['log_loss_delta'],[0,0])
        swapped=list(reversed(rows))
        with self.assertRaisesRegex(ValueError,'unpaired'):bootstrap_deltas(rows,swapped)

    def test_result_payload_excluded_from_inference(self):
        row=build_rows([race('r','20260101')],[],{})[0]
        self.assertNotIn('winner_ids',model_input(row))
        self.assertNotIn('results',model_input(row,True))

if __name__ == '__main__':unittest.main()
