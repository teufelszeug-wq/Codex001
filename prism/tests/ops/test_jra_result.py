"""Synthetic official-layout fixtures; these are not real-race execution evidence."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from prism_ops.official import OfficialSourceError, jra_url_identity, parse_jra_result

URL = 'https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde1003202603021120261108/0A'
HTML = '''<div class="race_header"><div class="date">2026年11月8日(日曜) 3回福島2日</div>
<div class="race_number"><img alt="11レース"></div><span class="race_name">合成試験杯</span></div>
<table><thead><tr><th class="place">着順</th><th class="horse">馬名</th></tr></thead><tbody>
<tr><td class="place">1</td><td class="num">2</td><td class="horse">合成馬甲</td></tr>
<tr><td class="place">1</td><td class="num">4</td><td class="horse">合成馬乙</td></tr>
<tr><td class="place">3</td><td class="num">6</td><td class="horse">合成馬丙</td></tr></tbody></table>
<div class="refund_unit"><ul><li><dl><dt>単勝</dt><dd>
<div class="line"><div class="num">2</div><div class="yen">260円</div></div>
<div class="line"><div class="num">4</div><div class="yen">340円</div></div></dd></dl></li>
<li><dl><dt>馬連</dt><dd><div class="line"><div class="num">4-2</div><div class="yen">1,240円</div></div></dd></dl></li>
<li><dl><dt>馬単</dt><dd><div class="line"><div class="num">4-2</div><div class="yen">2,480円</div></div></dd></dl></li>
<li><dl><dt>枠連</dt><dd><div class="line"><div class="num"><span>1</span><span>1</span></div><div class="yen">520円</div></div></dd></dl></li>
<li><dl><dt>3連複</dt><dd><div class="line"><div class="num">－</div><div class="yen">－</div></div></dd></dl></li>
</ul></div>'''


class JraResultTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def snapshot(self, body=HTML, url=URL):
        data = body.encode()
        path = Path(self.temp.name) / (sha256(data).hexdigest() + '.html')
        path.write_bytes(data)
        return {'authority': 'JRA', 'official_url': url, 'body_path': str(path),
                'captured_at': '2026-11-08T08:00:00+00:00', 'source_sha256': sha256(data).hexdigest(),
                'encoding': 'utf-8', 'mode': 'SYNTHETIC'}

    def result(self, body=HTML, url=URL, **kwargs):
        return parse_jra_result(self.snapshot(body, url), expected_date='2026-11-08',
                                expected_venue='福島', expected_race_no=11,
                                expected_race_name='合成試験杯', **kwargs)

    def test_reuses_both_published_jra_result_routes_with_canonical_ids(self):
        self.assertEqual(jra_url_identity(URL, result=True),
                         jra_url_identity(URL.replace('pw01sde10', 'pw01sde01'), result=True))
        result = self.result()
        self.assertEqual(result['race_id'], 'JRA-20261108-03-11')
        self.assertEqual(result['mode'], 'SYNTHETIC')
        self.assertIsNone(result['published_at'])
        self.assertEqual(result['publication_status'], 'UNKNOWN_TIMESTAMP')
        self.assertEqual(result['first_observed_at'], '2026-11-08T08:00:00+00:00')
        self.assertEqual(len(result['source_snapshot']['normalized_sha256']), 64)

    def test_dead_heat_all_winners_and_ordered_unordered_frame_tickets(self):
        result = self.result()
        self.assertEqual([r['horse_no'] for r in result['finishers'] if r['finish'] == 1], [2, 4])
        self.assertEqual(result['payouts'][2]['horse_nos'], [2, 4])
        self.assertEqual(result['payouts'][3]['horse_nos'], [4, 2])
        self.assertEqual(result['payouts'][4]['frame_nos'], [1, 1])
        self.assertEqual(result['complete_bet_types'], ['EXACTA', 'FRAME_QUINELLA', 'QUINELLA', 'WIN'])
        self.assertTrue(result['settlement_ready'])

    def test_cancellation_retains_payouts_but_holds_unlisted_losses(self):
        result = self.result(HTML.replace('class="place">3', 'class="place">取消'))
        self.assertEqual(result['finishers'][-1]['status'], 'SCRATCHED')
        self.assertFalse(result['complete_payouts'])
        self.assertFalse(result['settlement_ready'])
        self.assertEqual(result['complete_bet_types'], [])
        self.assertTrue(result['payouts'])

    def test_wrong_race_and_missing_or_tampered_bytes_fail(self):
        for body in [HTML.replace('3回福島2日', '3回東京2日'),
                     HTML.replace('2026年11月8日', '2026年11月9日'),
                     HTML.replace('11レース', '10レース'), HTML.replace('class="refund_unit"', 'class="changed"')]:
            with self.subTest(body=body[:40]), self.assertRaises(OfficialSourceError):
                self.result(body)
        snapshot = self.snapshot()
        Path(snapshot['body_path']).write_text('changed')
        with self.assertRaises(OfficialSourceError):
            parse_jra_result(snapshot, expected_date='2026-11-08', expected_venue='福島', expected_race_no=11)
        with self.assertRaises(OfficialSourceError):
            self.result(url=URL.replace('20261108', '20261109'))

    def test_incomplete_dead_heat_dividends_duplicate_or_bad_amounts_fail(self):
        missing = '<div class="line"><div class="num">4</div><div class="yen">340円</div></div>'
        for body in [HTML.replace(missing, ''), HTML.replace('260円', '0円'),
                     HTML.replace('260円', '返還'), HTML.replace('class="num">6', 'class="num">4'),
                     HTML.replace('4-2</div>', '4-9</div>')]:
            with self.subTest(body=body[-70:]), self.assertRaises(OfficialSourceError):
                self.result(body)


if __name__ == '__main__':
    unittest.main()
