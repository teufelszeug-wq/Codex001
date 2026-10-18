import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/research'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from b0_worker import predict
from run_b0_research import run

class B0Tests(unittest.TestCase):
    def request(self):
        return {'race_id':'TEST|20260101|X|1','date':'20260101','start':'1000','surface':'DIRT','runners':[
            {'horse_no':1,'history':[{'date':'20251201','start':'1000','surface':'DIRT','score':80}]},
            {'horse_no':2,'history':[]}]}
    def test_results_and_market_rejected(self):
        for key in ('results','odds'):
            r=self.request();r[key]=1
            with self.assertRaises(ValueError):predict(r)
    def test_future_and_same_cutoff_history_rejected(self):
        for date in ('20260101','20260102'):
            r=self.request();r['runners'][0]['history'][0]['date']=date
            with self.assertRaises(ValueError):predict(r)
    def test_cold_prior_and_mass(self):
        result=predict(self.request());self.assertAlmostEqual(sum(result['p_win'].values()),1)
        self.assertEqual(result['cold_start_horse_nos'],[2]);self.assertEqual(result['pick'],1)
    def test_same_time_result_changes_do_not_change_locked_predictions(self):
        def race(no):
            return {'race_id':f'TEST|20260101|X|{no}','date':'20260101','start':'1000','surface':'DIRT',
                    'entrants':[{'number':n,'identity':f'h{n}'} for n in (1,2)],
                    'results':[{'number':1,'rank':1,'status':'1'},{'number':2,'rank':2,'status':'2'}],
                    'win_payouts':{'1':200,'2':300}}
        rows=[race(1),race(2)];changed=copy.deepcopy(rows)
        changed[0]['results'][0]['rank']=2;changed[0]['results'][1]['rank']=1
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a';b=Path(d)/'b';run(rows,[],a);run(changed,[],b)
            self.assertEqual((a/'predictions.jsonl').read_bytes(),(b/'predictions.jsonl').read_bytes())

if __name__=='__main__':unittest.main()
