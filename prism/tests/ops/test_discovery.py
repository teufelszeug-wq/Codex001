"""Synthetic navigation fixtures, never forecasts or official live-source claims."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from prism_ops.discovery import (discover_official_races, parse_jra_navigation,
                                 parse_nar_calendar, parse_nar_navigation)
from prism_ops.official import OfficialSourceError

JRA_INDEX = 'https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dli00%2FF3'
JRA_CARD = 'https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202605041120261115/4C'
NAR_CAL = 'https://www.keiba.go.jp/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop?k_year=2026&k_month=11'
NAR_MENU = 'https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceList?k_babaCode=31&k_raceDate=2026%2F11%2F15'
NAR_CARD = '/KeibaWeb/TodayRaceInfo/DebaTable?k_babaCode=31&k_raceDate=2026%2F11%2F15&k_raceNo=1'
MENU = f'''<section class="raceTable"><table><tbody>
<tr><th colspan="13">2026年11月15日(日) 高知競馬 当日メニュー</th></tr>
<tr class="data"><td>1R</td><td>14:55</td><td></td><td></td><td><a href="{NAR_CARD.replace('&', '&amp;')}">合成</a></td>
<td></td><td></td><td></td><td></td><td></td></tr>
<tr class="data"><td>1R</td><td>2</td><td>合成馬</td><td>騎手変更</td><td>疾病</td><td>変更前→変更後</td></tr>
</tbody></table></section>'''


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def snapshot(self, body, url, authority='JRA'):
        data = body.encode()
        path = Path(self.temp.name) / (sha256(data).hexdigest() + '.html')
        path.write_bytes(data)
        return {'authority': authority, 'official_url': url, 'requested_url': url,
                'body_path': str(path), 'captured_at': '2026-11-14T01:00:00Z',
                'source_sha256': sha256(data).hexdigest(), 'encoding': 'utf-8', 'mode': 'SYNTHETIC'}

    def test_published_jra_links_actions_and_external_link_exclusion(self):
        body = f'''<div id="contentsBody"><a href="{JRA_CARD}">11R</a>
        <a href="#contentsBody">同一ページ内</a><a href="#" onclick="return doAction('/JRADB/accessD.html', 'pw01drl00052026050420261115/BD');">メニュー</a>
        <a href="https://evil.test/JRADB/accessD.html?CNAME=pw01dde0108202605041020261115/AA">外部</a></div>'''
        parsed = parse_jra_navigation(self.snapshot(body, JRA_INDEX), dates=['2026-11-15'])
        self.assertEqual([r['race_id'] for r in parsed['candidates']], ['JRA-20261115-08-11'])
        self.assertFalse(parsed['candidates'][0]['official_input_verified'])
        self.assertEqual(len(parsed['menus']), 1)
        self.assertTrue(parsed['menus'][0]['form_navigation_observed'])
        self.assertTrue(Path(parsed['candidates'][0]['source_snapshot']['body_path']).is_file())

    def test_nar_menu_ignores_change_table_and_checks_header_and_link(self):
        snapshot = self.snapshot(MENU, NAR_MENU, 'NAR')
        candidates = parse_nar_navigation(snapshot, expected_date='2026-11-15', expected_venue='31')
        self.assertEqual([r['race_id'] for r in candidates], ['NAR-20261115-31-01'])
        for body in [MENU.replace('高知', '佐賀'), MENU.replace('k_babaCode=31', 'k_babaCode=32')]:
            with self.assertRaises(OfficialSourceError):
                parse_nar_navigation(self.snapshot(body, NAR_MENU, 'NAR'), expected_date='2026-11-15', expected_venue='31')

    def calendar(self, *, link=True):
        cells = ['<td>高知</td>'] + ['<td></td>'] * 14 + [f'<td><a href="{NAR_MENU}">開催</a></td>' if link else '<td>開催</td>']
        return '<select name="k_year"><option value="2026" selected>2026</option></select><a id="monthTab11" class="active"></a><table class="schedule"><tr>' + ''.join(cells) + '</tr></table>'

    def test_nar_calendar_preserves_unavailable_menu_as_a_gap(self):
        value = parse_nar_calendar(self.snapshot(self.calendar(), NAR_CAL, 'NAR'), expected_date='2026-11-15')
        self.assertEqual(value['menus'][0]['official_url'], NAR_MENU)
        value = parse_nar_calendar(self.snapshot(self.calendar(link=False), NAR_CAL, 'NAR'), expected_date='2026-11-15')
        self.assertEqual(value['menus'], [])
        self.assertEqual(value['errors'][0]['code'], 'NAR_MENU_LINK_UNAVAILABLE')

    def test_discovery_injected_reader_is_forced_synthetic_and_incomplete_not_verified(self):
        body = f'<div id="contentsBody"><a href="{JRA_CARD}">11R</a></div>'
        def reader(url, directory, **options):
            snapshot = self.snapshot(body, url)
            snapshot['mode'] = 'LIVE_FETCH'  # Test readers cannot establish real collection.
            return snapshot
        report = discover_official_races('JRA', ['2026-11-15'], self.temp.name, fetcher=reader)
        self.assertEqual(report['candidate_count'], 1)
        self.assertEqual(report['verified_forecasts'], 0)
        self.assertFalse(report['official_input_verified'])
        self.assertEqual(report['source_snapshots'][0]['mode'], 'SYNTHETIC')
        self.assertIn('JRA_RACE_SLOTS_INCOMPLETE', [r['code'] for r in report['errors']])

    def test_unpublished_or_changed_bytes_are_errors_not_guessed_candidates(self):
        def reader(url, directory, **options):
            return self.snapshot('<html>情報がありません</html>', url)
        report = discover_official_races('JRA', ['2026-11-15'], self.temp.name, fetcher=reader)
        self.assertEqual(report['candidate_count'], 0)
        self.assertEqual(report['status'], 'INCOMPLETE')
        snapshot = self.snapshot(f'<a href="{JRA_CARD}">race</a>', JRA_INDEX)
        Path(snapshot['body_path']).write_text('tampered')
        with self.assertRaises(OfficialSourceError):
            parse_jra_navigation(snapshot, dates=['2026-11-15'])


if __name__ == '__main__':
    unittest.main()
