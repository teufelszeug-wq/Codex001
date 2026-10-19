from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from census_model_readiness import build_report,census,digest,raw_archive_census,extract_hold_store
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import json


def race(date='20260101',start='1000',identifier='one'):
    return {'race_id':identifier,'date':date,'start':start,'authority':'TEST','surface':'DIRT','venue':'TEST',
            'distance':1200,'direction':'RIGHT','entrants':[{'number':1,'identity':'a','frame':None,'weight':55,'career':{}},
            {'number':2,'identity':'b','frame':2,'weight':54,'career':{'全成績':[0,0,0,0]}}],
            'results':[{'number':1,'rank':1,'status':'1'},{'number':2,'rank':2,'status':'2'}],'win_payouts':{'1':100},'source':'PRIVATE'}


class CensusTests(unittest.TestCase):
    def test_presence_denominators_and_missing_rates(self):
        result=census([race()])['features']
        self.assertEqual(result['frame_number']['available_count'],1)
        self.assertEqual(result['frame_number']['missing_rate'],.5)
        self.assertEqual(result['career_all_aggregate']['available_count'],1)
        self.assertEqual(result['workout_observations']['available_count'],0)

    def test_carried_weight_is_never_body_condition(self):
        values=census([race()])['features']
        self.assertEqual(values['carried_weight']['available_count'],2)
        self.assertEqual(values['body_condition_observations']['available_count'],0)

    def test_current_results_are_not_past_history(self):
        values=census([race()])['features']
        self.assertEqual(values['result_rank_labels_post_only']['available_count'],1)
        self.assertEqual(values['base_ability_ordinal_proxy']['available_count'],0)

    def test_same_start_batch_never_updates_history_between_races(self):
        first=race(identifier='a');second=race(identifier='b')
        values=census([first,second])['features']
        self.assertEqual(values['base_ability_ordinal_proxy']['available_count'],0)

    def test_earlier_batch_is_counted_but_not_prior_day_certified(self):
        first=race(identifier='a');second=race(start='1100',identifier='b')
        values=census([first,second])['features']
        self.assertEqual(values['base_ability_ordinal_proxy']['available_count'],2)
        self.assertEqual(values['base_ability_prior_day_proxy']['available_count'],0)
        self.assertEqual(values['base_ability_ordinal_proxy']['historical_timestamp_certified_count'],0)

    def test_bootstrap_leakage_rejected(self):
        with self.assertRaisesRegex(ValueError,'bootstrap chronology'):census([race()],[race(identifier='bootstrap')])

    def test_nonmatching_surface_is_not_ability_coverage(self):
        bootstrap=race(date='20251231');bootstrap['surface']='TURF'
        values=census([race()],[bootstrap])['features']
        self.assertEqual(values['base_ability_ordinal_proxy']['available_count'],0)
        self.assertEqual(values['rotation_days_derived']['available_count'],2)

    def test_report_has_no_names_raw_paths_or_records(self):
        january=race();january['entrants'][0]['name']='PRIVATE_HORSE'
        report=build_report([january],[race(date='20251231',identifier='dec')],{})
        representation=str(report)
        self.assertNotIn('PRIVATE_HORSE',representation);self.assertNotIn('PRIVATE',representation)
        self.assertNotIn('entrants',report['january'])
        self.assertFalse(report['phase_b_empirical_model_complete'])
        self.assertEqual(report['report_hash'],digest({k:v for k,v in report.items() if k!='report_hash'}))

    def test_source_path_does_not_change_canonical_dataset_hash(self):
        first=race();second=deepcopy(first);second['source']='ANOTHER_PRIVATE_PATH'
        self.assertEqual(census([first])['canonical_dataset_hash'],census([second])['canonical_dataset_hash'])

    def test_duplicate_races_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate race'):census([race(),race()])

    def test_wrong_month_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'January universe'):build_report([race(date='20260201')],[],{})

    def test_raw_image_frame_and_marked_weight_are_counted_without_names(self):
        with TemporaryDirectory() as folder:
            page=Path(folder)/'jra_racingviewer/20260101/one.htm';page.parent.mkdir(parents=True)
            page.write_text('<table class="striped"><tr><td class="num">1</td><td class="waku"><img alt="枠2黒"></td><td class="weight">☆54.0</td><td class="h_weight">472(+12)</td><td class="jockey">PRIVATE_RIDER</td><td class="f_time">36.2</td></tr></table>')
            report=raw_archive_census(folder);values=report['authorities']['JRA']['features']
            self.assertEqual(values['frame_recoverable']['available_count'],1)
            self.assertEqual(values['carried_weight_recoverable']['available_count'],1)
            self.assertEqual(values['body_weight_change_observation']['available_count'],1)
            self.assertNotIn('PRIVATE_RIDER',str(report))

    def test_extraction_covers_universe_and_keeps_unknown_times_in_private_store(self):
        with TemporaryDirectory() as folder:
            root=Path(folder);race_row=race();race_row['authority']='NAR'
            raw='競走年月日,競馬場,レース番号,馬番,枠番,負担重量,騎手名,着順\n20260101,TEST,1,1,1,55,SYNTHETIC,1\n20260101,TEST,1,2,2,54,SYNTHETIC,2\n'
            race_row['venue']='TEST';race_row['number']=1
            with ZipFile(root/'nar_202601_official.zip','w') as archive:archive.writestr('synthetic_horselist.csv',raw)
            report=extract_hold_store(root,[race_row],root/'hold')
            self.assertEqual(report['candidate_count'],2);self.assertTrue(report['coverage_complete'])
            self.assertEqual(report['engine_ready_count'],0)
            self.assertEqual(report['unknown_availability_count'],2)
            records=[json.loads(p.read_text()) for p in (root/'hold').glob('*.json')]
            self.assertEqual(len(records),2)
            self.assertTrue(all(r['source']['available_at'] is None for r in records))
            self.assertTrue(all('着順' not in str(r) for r in records))
            with self.assertRaises(FileExistsError):extract_hold_store(root,[race_row],root/'hold')


if __name__=='__main__':unittest.main()
