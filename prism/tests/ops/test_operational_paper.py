import json
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

from prism_engine.contracts import digest
from prism_ops.paper import render_operational_html, render_operational_paper, confirm_visual_qa


def paper_fixture(horses=3, agents=2, long=False):
    runners = [{'horse_id': 'h' + str(n), 'horse_no': n, 'frame_no': (n - 1) % 8 + 1,
                'name': '架空馬' + str(n) + ('ヴェルサイユノユメ' if long else '')} for n in range(1, horses + 1)]
    def record(agent, stage):
        return {'mode': 'single_model_simulation', 'saved_at': '2026-11-14T17:00:00+09:00',
                'diagnoses': [{'horse_id': r['horse_id'], 'reason': '人工検証用の全頭診断。' + ('長文の根拠を省略せず紙面に掲載する。' * 35 if long and r['horse_no'] == 1 else '')} for r in runners],
                'picks': [{'horse_id': 'h1', 'mark': '◎', 'reason': '人工検証の印。'}],
                'tickets': [{'type': 'WIN', 'horse_nos': [1], 'stake_yen': 200}],
                'change_reason': '人工検証の段階変更。' if stage == 'final' else ''}
    return {'mode': 'SYNTHETIC', 'race': {'race_id': 'synthetic-paper', 'race_name': '架空紙面検証競走',
            'authority': 'JRA', 'start_at': '2026-11-15T15:40:00+09:00', 'runners': runners},
            'characters': {'a' + str(a): {'name': '架空専門' + str(a)} for a in range(agents)},
            'preliminary': {'a' + str(a): record(a, 'initial') for a in range(agents)},
            'final': {'a' + str(a): record(a, 'final') for a in range(agents)},
            'discussions': [{'topic_id': str(t), 'title': '議題' + str(t), 'moderator_id': 'editor',
                             'started_at': '2026-11-14T16:00:00+09:00', 'completed_at': '2026-11-14T16:30:00+09:00',
                             'turns': [{'forecaster_id': 'a' + str(a), 'text': '議題' + str(t) + '発言' + str(a) + '：人工的な検証発言です。', 'evidence_refs': ['synthetic-source']}
                                       for a in range(agents)]} for t in range(5)]}


class OperationalPaperTests(unittest.TestCase):
    def test_all_forecasters_horses_topics_and_turns_retained(self):
        bundle = paper_fixture(18, 19, long=True)
        html = render_operational_html(bundle)
        payload = html.split('<script id="paper-data" type="application/json">', 1)[1].split('</script>', 1)[0]
        blocks = json.loads(payload)
        text = ''.join(b['text'] for b in blocks)
        for topic in bundle['discussions']:
            for turn in topic['turns']:
                self.assertIn(turn['text'], text)
        self.assertIn('架空専門18', html)
        self.assertIn('人工入力', text)
        self.assertEqual(text.count('人工検証用の全頭診断。'), 18 * 19 * 2)
        self.assertIn('200円', text)

    def test_untrusted_text_cannot_inject_script(self):
        bundle = paper_fixture()
        bundle['discussions'][0]['turns'][0]['text'] = '</script><script>alert(1)</script>'
        html = render_operational_html(bundle)
        self.assertNotIn('</script><script>alert(1)</script>', html)
        self.assertIn('\\u003c/script\\u003e', html)

    def test_missing_horse_identity_rejected(self):
        bundle = paper_fixture()
        bundle['race']['runners'][0]['horse_id'] = None
        with self.assertRaises(ValueError):
            render_operational_html(bundle)

    def test_day_correction_keeps_pre_day_reference_and_names_scratched_horse(self):
        bundle = paper_fixture()
        scratched = bundle['race']['runners'].pop()
        bundle['race']['scratched_runners'] = [dict(scratched, status='SCRATCHED')]
        bundle.update(edition_kind='DAY_CORRECTION', base_edition='pre-v1',
                      base_bundle_hash='a' * 64, changes={'body_weight': {'h1': 480}, 'scratches': [scratched['horse_id']]},
                      change_reason='公式馬体重と取消の発表を反映。')
        html = render_operational_html(bundle)
        self.assertIn('当日差分', html)
        self.assertIn('前日一次予想', html)
        self.assertIn('前日座談会', html)
        self.assertIn('当日差分最終予想', html)
        self.assertIn('公式取消', html)
        self.assertIn('架空馬3', html)
        self.assertIn('a' * 64, html)

    def test_editor_role_forecast_byline_and_moderator_name_are_distinct(self):
        bundle = paper_fixture(3, 2)
        editor_id = 'canonical-editor-uuid'
        bundle['characters'][editor_id] = {'name': '篠宮律', 'role': 'editor'}
        for stage in ('preliminary', 'final'):
            bundle[stage][editor_id] = bundle[stage].pop('a0')
        bundle['discussions'][0]['moderator_id'] = editor_id
        before = digest(bundle)
        html = render_operational_html(bundle)
        self.assertIn('一次予想　本紙（編集部）', html)
        self.assertIn('最終予想　本紙（編集部）', html)
        self.assertIn('司会 篠宮律', html)
        self.assertNotIn('一次予想　篠宮律', html)
        self.assertEqual(before, digest(bundle))
        bundle['characters'][editor_id]['role'] = 'specialist'
        html = render_operational_html(bundle)
        self.assertIn('一次予想　篠宮律', html)
        self.assertNotIn('一次予想　本紙（編集部）', html)

    def test_pre_available_render_is_a_candidate_until_publication_gate(self):
        bundle = paper_fixture()
        bundle['mode'] = 'PRE_AVAILABLE'
        html = render_operational_html(bundle)
        self.assertIn('発走前の発行候補', html)
        self.assertIn('正式な前日発行は発行判定記録を参照', html)
        self.assertNotIn('前日版。発行後の変更', html)

    @unittest.skipUnless(shutil.which('chromium') and importlib.util.find_spec('fitz'), 'Chromium and PyMuPDF required')
    def test_real_pdf_and_all_pdf_page_pngs_keep_review_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = render_operational_paper(paper_fixture(18, 2, long=True), Path(directory) / 'paper')
            self.assertEqual(manifest['content_hash'], digest(paper_fixture(18, 2, long=True)))
            self.assertEqual(manifest['qa']['status'], 'EXECUTED')
            self.assertIsNone(manifest['qa']['reviewer'])
            self.assertTrue(manifest['qa']['mechanical_checks']['passed'])
            self.assertGreater(len(manifest['images']), 1)
            self.assertTrue(Path(manifest['pdf']['path']).read_bytes().startswith(b'%PDF'))
            # This fixture deliberately does not claim a visual review. The
            # promotion function is exercised for integrity, then excluded from
            # real-world publication/performance counters.
            reviewed = confirm_visual_qa(manifest, 'SYNTHETIC_TEST_REVIEWER', 'Synthetic approval API test, not a real newspaper review.')
            self.assertEqual(reviewed['qa']['status'], 'VERIFIED')
            self.assertEqual(manifest['qa']['status'], 'EXECUTED')
            Path(manifest['images'][0]['path']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                confirm_visual_qa(manifest, 'reviewer', 'all-page review')


if __name__ == '__main__':
    unittest.main()
