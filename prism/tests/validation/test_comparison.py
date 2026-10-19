from copy import deepcopy
import math
import json
import tempfile
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from prism_validation.compare import compare_runs, losses, summarize, digest, load_archived, load_b0
from prism_validation.experiments import chronological_calibration, archived_experts


def row(key='r1',date='20260101',prob=.8,payout=0,refund=0):
    return {'race_id':key,'order_key':[date,'1000',key], 'probabilities':{'a':prob,'b':1-prob},
            'winners':['a'],'stake_yen':100,'payout_excluding_refund_yen':payout,
            'refund_yen':refund,'prediction_hash':'synthetic','pick':'a'}


class Comparisons(unittest.TestCase):
    def test_metrics_known_answer(self):
        ll,brier=losses({'a':.8,'b':.2},['a'])
        self.assertAlmostEqual(ll,-math.log(.8));self.assertAlmostEqual(brier,.08)
    def test_fractional_dead_heat(self):
        ll,brier=losses({'a':.5,'b':.5},['a','b'])
        self.assertAlmostEqual(ll,math.log(2));self.assertEqual(brier,0)
    def test_refund_not_double_counted(self):
        m=summarize([row(refund=100),row('r2',payout=350)])
        self.assertEqual(m['profit_yen'],250);self.assertEqual(m['effective_return_rate'],3.5)
    def test_all_refund_null_roi(self):
        self.assertIsNone(summarize([row(refund=100)])['effective_return_rate'])
    def test_refund_payout_conflict(self):
        with self.assertRaises(ValueError):summarize([row(refund=100,payout=100)])
    def test_drawdown_known_answer(self):
        m=summarize([row('a',payout=300),row('b'),row('c'),row('d',payout=500)])
        self.assertEqual(m['max_drawdown_yen'],200)
    def test_duplicate_race_rejected(self):
        with self.assertRaises(ValueError):compare_runs({'a':[row(),row()],'b':[row()]})
    def test_coverage_intersection(self):
        x=compare_runs({'a':[row(),row('r2')],'b':[row()]})
        self.assertEqual(x['coverage']['paired_races'],1)
        self.assertEqual(x['coverage']['excluded_noncommon_by_run']['a'],1)
    def test_outcomes_cannot_differ(self):
        b=row();b['winners']=['b']
        with self.assertRaises(ValueError):compare_runs({'a':[row()],'b':[b]})
    def test_probabilities_rejected(self):
        for p in (float('nan'),-1,2):
            with self.assertRaises(ValueError):losses({'a':p,'b':1-p},['a'])
    def test_deterministic_hash_order(self):
        a=[row(),row('r2')]
        x=compare_runs({'a':a,'b':deepcopy(a)})
        y=compare_runs({'b':list(reversed(a)),'a':list(reversed(a))})
        self.assertEqual(x['report_hash'],y['report_hash'])
        self.assertEqual(x['report_hash'],digest({k:v for k,v in x.items() if k!='report_hash'}))
    def test_calibration_does_not_select_using_holdout(self):
        a=row();b=row('r2','20260120');first=chronological_calibration([a,b])
        b['winners']=['b'];second=chronological_calibration([a,b])
        self.assertEqual(first['frozen_artifact'],second['frozen_artifact'])
        self.assertNotEqual(first['holdout_after']['log_loss'],second['holdout_after']['log_loss'])
    def test_exhaustive_dates_required(self):
        with self.assertRaises(ValueError):chronological_calibration([row(),row('r2','20260201')])
    def test_archive_hash_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'predictions').mkdir();(root/'reviews').mkdir()
            p={'race_id':'r','probabilities':{'win':{'a':.8,'b':.2}},
               'tickets':[{'type':'WIN','number':1,'stake_yen':100}]}
            p['lock_hash']=digest(p)
            ll,brier=losses(p['probabilities']['win'],['a'])
            review={'race_id':'r','prediction_hash':p['lock_hash'],'pick':1,'winners':['a'],
                    'date':'20260101','start':'1000','stake_yen':100,'refund_yen':0,
                    'payout_yen':0,'profit_yen':-100,'log_loss':ll,'brier':brier}
            event={'seq':0,'previous_hash':'0'*64,'event':'REVIEW_AND_LEARN',
                   'payload':{'race_id':'r','review_hash':digest(review)}}
            event['hash']=digest(event)
            (root/'events_000.jsonl').write_text(json.dumps(event)+'\n')
            (root/'race_index.json').write_text(json.dumps([{'race_id':'r','file':'1.json'}]))
            (root/'predictions/1.json').write_text(json.dumps(p))
            (root/'reviews/1.json').write_text(json.dumps(review))
            self.assertEqual(len(load_archived(root)),1)
            p['probabilities']['win']={'a':.7,'b':.3}
            (root/'predictions/1.json').write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'prediction content hash'):load_archived(root)
    def test_event_chain_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            event={'seq':0,'previous_hash':'0'*64,'event':'REVIEW_AND_LEARN',
                   'payload':{'race_id':'r','review_hash':'bad'},'hash':'bad'}
            (root/'events_000.jsonl').write_text(json.dumps(event)+'\n')
            with self.assertRaisesRegex(ValueError,'event chain'):load_archived(root)
    def test_b0_simultaneous_profit_payout_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);ref=row()
            pred={'race_id':'r1','p_win':ref['probabilities'],'pick':1,'stake_yen':100}
            pred['prediction_hash']=digest(pred)
            ll,brier=losses(ref['probabilities'],ref['winners'])
            ev={'race_id':'r1','prediction_hash':pred['prediction_hash'],'stake_yen':100,
                'payout_excluding_refund_yen':0,'refund_yen':0,'profit_yen':-100,'log_loss':ll,'brier':brier}
            events=[];previous='0'*64
            for name,payload in [('PREDICTION_LOCK',{'race_id':'r1','prediction_hash':pred['prediction_hash']}),
                                 ('RESULT_REVEAL',{'race_id':'r1','evaluation_hash':digest(ev)}),
                                 ('HISTORY_UPDATE',{'race_id':'r1'})]:
                event={'event':name,'payload':payload,'previous_hash':previous}
                event['hash']=digest(event);previous=event['hash'];events.append(event)
            (root/'predictions.jsonl').write_text(json.dumps(pred)+'\n')
            (root/'evaluations.jsonl').write_text(json.dumps(ev)+'\n')
            (root/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            self.assertEqual(len(load_b0(root,[ref])),1)
            ev['payout_excluding_refund_yen']=100000;ev['profit_yen']=99900
            (root/'evaluations.jsonl').write_text(json.dumps(ev)+'\n')
            with self.assertRaisesRegex(ValueError,'evaluation content hash'):load_b0(root,[ref])
    def test_expert_standalone_hash_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'predictions').mkdir();ref=row()
            pred={'race_id':'r1','experts':{'test':ref['probabilities']}}
            pred['lock_hash']=digest(pred);ref['prediction_hash']=pred['lock_hash']
            (root/'race_index.json').write_text(json.dumps([{'race_id':'r1','file':'1.json'}]))
            (root/'predictions/1.json').write_text(json.dumps(pred))
            self.assertEqual(archived_experts(root,[ref])['paired_races'],1)
            pred['experts']['test']={'a':.9,'b':.1}
            (root/'predictions/1.json').write_text(json.dumps(pred))
            with self.assertRaisesRegex(ValueError,'expert prediction content hash'):archived_experts(root,[ref])


if __name__=='__main__':unittest.main()
