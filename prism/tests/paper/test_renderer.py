from copy import deepcopy
from html.parser import HTMLParser
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests/engine')]

from prism_engine import predict, post_market, DEFAULT_CONFIG
from prism_engine.contracts import digest
from prism_paper import render_paper
from fixture import raw_fixture, market_fixture, seal


def fixture(raw=None):
    raw = raw_fixture() if raw is None else raw
    cfg = dict(DEFAULT_CONFIG, runs=30)
    pred = predict(raw, '2026-01-01T09:55:00+09:00', cfg)
    return {'schema': 'prism.engine.bundle/v1', 'raw': raw, 'prediction': pred,
            'market_values': post_market(pred, market_fixture(pred), cfg)}


class Inspector(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.pages = []
        self.horses = []
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        values = dict(attrs)
        if 'data-page' in values:
            self.pages.append(values['data-page'])
        if 'data-horse-id' in values:
            self.horses.append(values['data-horse-id'])


class PaperTests(unittest.TestCase):
    def setUp(self):
        self.bundle = fixture()

    def test_four_vertical_print_pages_and_all_horses(self):
        html = render_paper(self.bundle)
        parsed = Inspector(html)
        self.assertEqual(parsed.pages, ['1', '2', '3', '4'])
        self.assertEqual(parsed.horses, ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        self.assertIn('writing-mode:vertical-rl', html)
        self.assertIn('@page {size:A3 portrait', html)
        self.assertIn('馬名未収録', html)

    def test_horse_and_frame_numbers_are_not_aliased(self):
        html = render_paper(self.bundle)
        self.assertIn('枠番 1</b><b>馬番 2', html)
        self.assertIn('枠番 2</b><b>馬番 3', html)

    def test_stable_rendering(self):
        self.assertEqual(render_paper(self.bundle), render_paper(deepcopy(self.bundle)))

    def test_research_limitations_and_dialogue_absence_are_visible(self):
        html = render_paper(self.bundle)
        for text in ['人工入力・架空レース', '予測性能・収益性は未実証', '座談会未実施', '各点固定百円', '馬名未収録']:
            self.assertIn(text, html)

    def test_missing_raw_is_rejected_not_inferred(self):
        del self.bundle['raw']
        with self.assertRaises((ValueError, KeyError)):
            render_paper(self.bundle)

    def test_modified_raw_rejected(self):
        self.bundle['raw']['runners'][1]['horse_no'] = 9
        seal(self.bundle['raw'])
        with self.assertRaises(ValueError):
            render_paper(self.bundle)

    def test_modified_prediction_rejected(self):
        self.bundle['prediction']['scores']['h1'] = 999
        with self.assertRaises(ValueError):
            render_paper(self.bundle)

    def test_other_market_rejected(self):
        self.bundle['market_values']['prediction_hash'] = 'other'
        with self.assertRaises(ValueError):
            render_paper(self.bundle)

    def test_modified_plan_rejected(self):
        self.bundle['market_values']['plan']['stake_yen'] = 1
        with self.assertRaises(ValueError):
            render_paper(self.bundle)

    def test_post_result_bundle_rejected(self):
        self.bundle['settlement'] = {}
        with self.assertRaises(ValueError):
            render_paper(self.bundle)

    def test_other_discussion_rejected(self):
        with self.assertRaises(ValueError):
            render_paper(self.bundle, discussion={'race_id': 'other'})

    def test_bound_context_does_not_invent_dialogue(self):
        p = self.bundle['prediction']
        context = {'race_id': p['race_id'], 'input_hash': p['input_hash'], 'prediction_hash': p['lock_hash']}
        self.assertIn('座談会未実施', render_paper(self.bundle, discussion=context))

    def test_future_discussion_and_mode_change_rejected(self):
        p = self.bundle['prediction']
        context = {'race_id': p['race_id'], 'input_hash': p['input_hash'], 'prediction_hash': p['lock_hash'],
                   'recorded_at': '2026-01-01T10:01:00+09:00'}
        with self.assertRaises(ValueError):
            render_paper(self.bundle, discussion=context)
        del context['recorded_at']
        context['mode'] = 'PRE_AVAILABLE'
        with self.assertRaises(ValueError):
            render_paper(self.bundle, discussion=context)

    def test_dialogue_escape_and_role_simulation_warning(self):
        p = self.bundle['prediction']
        record = {'race_id': p['race_id'], 'input_hash': p['input_hash'], 'prediction_hash': p['lock_hash'],
                  'execution_mode': 'ROLE_SIMULATION', 'turns': [{'agent_id': 'RIO', 'text': '<script>bad()</script>'}]}
        html = render_paper(self.bundle, discussion=record)
        self.assertIn('独立ＡＩ未認証', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('script', Inspector(html).tags)

    def test_unbound_validation_cannot_claim_this_race_accuracy(self):
        html = render_paper(self.bundle, validation={'schema': 'other-aggregate'})
        self.assertIn('このレースの性能証明ではない', html)

    def test_comparison_integrity_and_scope(self):
        report = {'schema': 'prism.validation.comparison/v1', 'scope': 'ARCHIVED_JANUARY_RESEARCH_COMPARISON',
                  'coverage': {'paired_races': 1354}, 'strict_pit_certified_races': 0,
                  'runs': {'baseline': {'log_loss': 2.1, 'effective_return_rate': .63, 'profit_yen': -100}}}
        report['report_hash'] = digest(report)
        html = render_paper(self.bundle, validation=report)
        self.assertIn('旧一月研究方式の比較', html)
        self.assertIn('今回予想・新Ｂ全機能の性能証明ではない', html)
        self.assertIn('1354', html)
        report['runs']['baseline']['profit_yen'] = 100
        with self.assertRaises(ValueError):
            render_paper(self.bundle, validation=report)

    def test_without_market_no_candidates_are_invented(self):
        del self.bundle['market_values']
        self.assertIn('候補作成なし', render_paper(self.bundle))


if __name__ == '__main__':
    unittest.main()
