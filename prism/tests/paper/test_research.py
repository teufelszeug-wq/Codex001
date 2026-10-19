from copy import deepcopy
import unittest
from prism_engine.contracts import digest
from prism_paper import render_research_paper


def seal(value,key):
    value.pop(key,None)
    value[key]=digest(value)
    return value


def fixture():
    # Intentionally tiny, invented research records; no actual names in Git.
    dto=dict(schema='prism.paper.research-race/v1',race_id='synthetic',date='20260116',start='12:00',venue='試験',title='人工入力',distance_m=1600,surface='芝',direction='右',runners=[dict(horse_id='h1',horse_no=2,frame_no=1,name='<人工一号>',p_win=.6),dict(horse_id='h2',horse_no=3,frame_no=2,name='人工二号',p_win=.4)],mode='HISTORICAL_RECONSTRUCTION_NOT_PIT',strict_pit_certified=False,model_hash='model',prediction_hash='prediction',discussions=[])
    metric=dict(log_loss=2.1,brier=.8,calibration={'ece':.02},effective_return_rate=.6,profit_yen=-100,max_drawdown_yen=200)
    report=dict(schema='prism.validation.feature-experiment/v1',holdout_dates=['20260116','20260131'],training_races=653,holdout_races=701,models={'plus_both':{'model_hash':'model'}},runs={k:deepcopy(metric) for k in ('ability_only','plus_jockey','plus_body','plus_both')},missing_rates={'plus_both':{'body_change':.01}},strict_pit_certified_races=0)
    return seal(dto,'dto_hash'),seal(report,'report_hash')


class ResearchPaperTests(unittest.TestCase):
    def test_four_pages_full_roster_comparison_and_no_invented_dialogue(self):
        dto,report=fixture(); html=render_research_paper(dto,report)
        self.assertEqual(html.count('data-page='),4)
        for text in ('枠番 1','馬番 2','&lt;人工一号&gt;','座談会記録は未投入','Ｂｒｉｅｒ','最大ドローダウン','百円','writing-mode:vertical-rl'):
            self.assertIn(text,html)
        self.assertNotIn('<人工一号>',html)

    def test_dto_and_report_mutation_rejected(self):
        dto,report=fixture(); dto['runners'][0]['p_win']=.9
        with self.assertRaises(ValueError):render_research_paper(dto,report)
        dto,report=fixture();report['runs']['plus_both']['profit_yen']=999
        with self.assertRaises(ValueError):render_research_paper(dto,report)

    def test_roster_numbers_probabilities_mode_date_and_dialogue_guards(self):
        changes=[lambda d:d['runners'][1].update(horse_no=2),lambda d:d['runners'][0].update(frame_no=0),lambda d:d['runners'][0].update(p_win=.7),lambda d:d.update(mode='PRE_AVAILABLE'),lambda d:d.update(date='20260115'),lambda d:d.update(model_hash='other'),lambda d:d.update(discussions=[{'text':'invented'}])]
        for change in changes:
            dto,report=fixture();change(dto);seal(dto,'dto_hash')
            with self.subTest(dto=dto):
                with self.assertRaises(ValueError):render_research_paper(dto,report)


if __name__=='__main__':unittest.main()
