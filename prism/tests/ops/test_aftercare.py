"""Scoped mocked-service tests, not genuine publications/API/result executions."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path[:0]=[str(Path(__file__).resolve().parents[2]/'src')]
from prism_engine.contracts import digest
from prism_ops.aftercare import process_settlement_job
from prism_ops.official import OfficialSourceError
from prism_ops.store import Store


RACE='NAR-20261113-27-11'
URL='https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_babaCode=27&k_raceDate=2026%2F11%2F13&k_raceNo=11'
PRE='2026-11-12T20:00:00+09:00'
POST='2026-11-13T17:00:00+09:00'


class AftercareTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.clock=PRE
        self.store=Store(self.tmp.name,now=lambda:self.clock);self.addCleanup(self.store.close)
        self.bundle={'race':{'race_id':RACE,'authority':'NAR','race_name':'SYNTHETIC scoped fixture',
                             'start_at':'2026-11-13T16:15:00+09:00'}}
        self.store.save(RACE,'bundle','pre-v1',self.bundle)
        self.publication={'bundle_hash':digest(self.bundle),'published_at':PRE,'gate':{'ready':True}}
        # Only a unit-test service harness. Actual settle_saved is separately
        # exercised with an explicit SYNTHETIC entrypoint and rejects this.
        self.store.save(RACE,'publication','pre-v1',self.publication)
        self.clock=POST
        self.job={'race_id':RACE,'edition':'pre-v1','result_url':URL,'authority':'NAR',
                  'expected_date':'2026-11-13','expected_venue':'27','expected_race_no':11}
        self.source={'official_url':URL,'captured_at':POST,'source_sha256':'a'*64,
                     'mode':'LIVE_FETCH','authority':'NAR'}
        self.result={'race_id':RACE,'official_source':URL,'published_at':None,
                     'publication_status':'UNKNOWN_TIMESTAMP','first_observed_at':POST,
                     'mode':'OFFICIAL','status':'FINAL','payouts':[{'type':'WIN','horse_nos':[1],'payout_per_100_yen':350}],
                     'refunds':[],'complete_payouts':True,'complete_bet_types':['WIN'],
                     'race_identity':{'race_name':'SYNTHETIC scoped fixture'},
                     'source_snapshot':{'official_url':URL,'captured_at':POST,'source_sha256':'a'*64,
                                        'normalized_sha256':'b'*64}}
        self.settle_inputs=[]

    def fake_settle(self,store,race_id,result,*,edition,now):
        # A mocked downstream service; does not invoke genuine PRE settlement.
        self.settle_inputs.append(deepcopy(result))
        settlement={'settlement_id':digest(result),'edition':edition,'source_result_hash':digest(result),
                    'official_settlements':1,'summary':[]}
        store.save(race_id,'settlement',digest(result),settlement)
        return {'settlement':settlement,'official_settlements':1}

    def run_job(self,source=None,result=None,job=None,settler=None):
        with patch('prism_ops.aftercare.official.fetch_official_snapshot',return_value=deepcopy(source or self.source)) as fetch:
            with patch('prism_ops.aftercare.official.parse_nar_result',return_value=deepcopy(result or self.result)) as parse:
                with patch('prism_ops.aftercare.settle_saved',side_effect=settler or self.fake_settle):
                    report=process_settlement_job(job or self.job,self.store,now=lambda:self.clock)
        return report,fetch,parse

    def test_missing_publication_and_before_off_never_fetch_results(self):
        job={**self.job,'edition':'not-published'}
        report,fetch,_=self.run_job(job=job)
        self.assertEqual(report['status'],'PENDING_PUBLICATION');fetch.assert_not_called()
        self.clock='2026-11-13T16:14:00+09:00'
        report,fetch,_=self.run_job()
        self.assertEqual(report['status'],'NOT_DUE');fetch.assert_not_called()

    def test_identical_source_bytes_reuse_first_observation_and_no_duplicate_count(self):
        before=self.store.get(RACE,'bundle','pre-v1')
        first,_,parser=self.run_job()
        self.assertEqual(first['status'],'SETTLED');self.assertEqual(first['official_settlements'],1)
        parser.assert_called_once_with(self.source,expected_date='2026-11-13',expected_venue='27',expected_race_no=11)
        self.clock='2026-11-13T18:00:00+09:00'
        later_source={**self.source,'captured_at':self.clock}
        later_result=deepcopy(self.result);later_result['first_observed_at']=self.clock
        later_result['source_snapshot']['captured_at']=self.clock
        second,_,_=self.run_job(source=later_source,result=later_result)
        self.assertEqual(second['status'],'SKIPPED_SETTLED');self.assertEqual(second['official_settlements'],0)
        self.assertEqual(second['saved_official_settlements'],1)
        self.assertEqual(self.settle_inputs[0],self.settle_inputs[1])
        self.assertEqual(self.settle_inputs[1]['first_observed_at'],POST)
        self.assertEqual(before,self.store.get(RACE,'bundle','pre-v1'))

    def test_observed_correction_appends_version_without_replacing_original(self):
        self.run_job();original=self.settle_inputs[-1]
        self.clock='2026-11-13T18:00:00+09:00'
        source={**self.source,'source_sha256':'c'*64,'captured_at':self.clock}
        result=deepcopy(self.result);result['payouts'][0]['payout_per_100_yen']=400
        result['first_observed_at']=self.clock;result['source_snapshot'].update(source_sha256='c'*64,captured_at=self.clock)
        second,_,_=self.run_job(source=source,result=result)
        revised=self.settle_inputs[-1]
        self.assertEqual(second['result_revision'],2);self.assertEqual(second['official_settlements'],1)
        self.assertEqual(revised['correction_of'],original['source_snapshot']['normalized_sha256'])
        self.assertEqual(revised['revision_origin'],'LOCAL_OBSERVATION_SEQUENCE_NOT_OFFICIAL_REVISION')
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM artifacts WHERE kind='settlement'").fetchone()[0],2)

    def test_changed_html_without_changed_outcome_does_not_create_new_performance(self):
        self.run_job();original=self.settle_inputs[-1]
        source={**self.source,'source_sha256':'c'*64}
        result=deepcopy(self.result);result['source_snapshot']['source_sha256']='c'*64
        report,_,_=self.run_job(source=source,result=result)
        self.assertTrue(report['result_source_reused']);self.assertEqual(report['official_settlements'],0)
        self.assertEqual(original,self.settle_inputs[-1])

    def test_synthetic_source_identity_mismatch_and_wrong_title_never_settle(self):
        report,_,parser=self.run_job(source={**self.source,'mode':'SYNTHETIC'})
        self.assertEqual(report['status'],'BLOCKED');parser.assert_not_called();self.assertEqual(self.settle_inputs,[])
        result={**self.result,'race_id':'wrong-race'}
        report,_,_=self.run_job(result=result)
        self.assertEqual(report['status'],'BLOCKED');self.assertEqual(self.settle_inputs,[])
        report,_,_=self.run_job(job={**self.job,'expected_race_name':'different-title'})
        self.assertEqual(report['status'],'BLOCKED');self.assertEqual(self.settle_inputs,[])

    def test_incomplete_payout_failure_stays_blocked_with_zero_success(self):
        def incomplete(*args,**kwargs): raise ValueError('incomplete official payout coverage')
        report,_,_=self.run_job(settler=incomplete)
        self.assertEqual(report['status'],'BLOCKED');self.assertEqual(report['official_settlements'],0)
        self.assertIn('incomplete',report['reason'])

    def test_reflection_failure_keeps_successful_settlement(self):
        with patch('prism_ops.aftercare.reflect_saved',side_effect=RuntimeError('CONFIG_MISSING')):
            report,_,_=self.run_job(job={**self.job,'reflect':True})
        self.assertEqual(report['status'],'SETTLED_REFLECTION_BLOCKED')
        self.assertEqual(report['official_settlements'],1);self.assertEqual(report['saved_official_settlements'],1)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM artifacts WHERE kind='settlement'").fetchone()[0],1)
        with patch('prism_ops.aftercare.reflect_saved',return_value={'blocked':[{'status':'NOT_EXECUTED'}],'completed':[]}):
            retry,_,_=self.run_job(job={**self.job,'reflect':True})
        self.assertEqual(retry['official_settlements'],0);self.assertEqual(retry['saved_official_settlements'],1)

    def test_jra_result_adapter_receives_full_expected_identity(self):
        race_id='JRA-20261114-05-11';url='https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde0105202605031120261114/3E'
        bundle={'race':{'race_id':race_id,'authority':'JRA','start_at':'2026-11-14T15:30:00+09:00'}}
        self.clock='2026-11-13T20:00:00+09:00'
        self.store.save(race_id,'bundle','pre-v1',bundle)
        self.store.save(race_id,'publication','pre-v1',{'gate':{'ready':True},'bundle_hash':digest(bundle)})
        self.clock='2026-11-14T17:00:00+09:00'
        source={**self.source,'authority':'JRA','official_url':url,'captured_at':self.clock}
        result=deepcopy(self.result);result.update(race_id=race_id,official_source=url,first_observed_at=self.clock)
        result['source_snapshot'].update(official_url=url,captured_at=self.clock)
        job={**self.job,'race_id':race_id,'result_url':url,'authority':'JRA','expected_date':'2026-11-14',
             'expected_venue':'東京','expected_race_name':'SYNTHETIC scoped fixture'}
        with patch('prism_ops.aftercare.official.fetch_official_snapshot',return_value=source):
            with patch('prism_ops.aftercare.official.parse_jra_result',return_value=result) as parse:
                with patch('prism_ops.aftercare.settle_saved',side_effect=self.fake_settle):
                    report=process_settlement_job(job,self.store,now=lambda:self.clock)
        self.assertEqual(report['status'],'SETTLED')
        parse.assert_called_once_with(source,expected_date='2026-11-14',expected_venue='東京',expected_race_no=11,expected_race_name='SYNTHETIC scoped fixture')

    def test_unpublished_result_is_pending_but_wrong_identity_is_blocked(self):
        for error,status in [(OfficialSourceError('official payouts are not published or markup changed'),'PENDING_RESULT'),
                             (OfficialSourceError('official JRA result URL race identity mismatch'),'BLOCKED')]:
            with patch('prism_ops.aftercare.official.fetch_official_snapshot',return_value=self.source):
                with patch('prism_ops.aftercare.official.parse_nar_result',side_effect=error):
                    report=process_settlement_job(self.job,self.store,now=lambda:self.clock)
            self.assertEqual(report['status'],status);self.assertEqual(report['official_settlements'],0)


if __name__=='__main__':
    unittest.main()
