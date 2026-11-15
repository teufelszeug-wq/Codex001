from datetime import date
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from lxml import html

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from discover_official_races import jra_links, nar_racecard_links
from run_race_day import export_history, race_day_changes, restore_history
from run_forecast_batch import validate_panel_output


class RaceDayTests(unittest.TestCase):
    def test_jra_catalog_uses_official_navigation(self):
        page = html.fromstring("""
          <div id="contentsBody">
          <a href="/JRADB/accessD.html?CNAME=pw01dde0108202605041120261115/4C">11R</a>
          <a href="#" onclick="return doAction('/JRADB/accessD.html', 'pw01drl00052026050420261115/BD');">メニュー</a>
          <a href="https://example.test/JRADB/accessD.html?CNAME=pw01dde0108202605041020261115/97">外部</a>
          </div>
        """)
        self.assertEqual([key for key, _, _ in jra_links(page)],
                         [('20261115', 'KYOTO', 11), ('20261115', None, None)])

    def test_nar_does_not_count_the_runner_change_table_as_a_race(self):
        page = html.fromstring("""
          <div><section class="raceTable"><table><tbody>
            <tr><th colspan="13">2026年11月15日（日） 高知競馬 当日メニュー</th></tr>
            <tr class="data"><td>1R</td><td>14:55</td><td></td><td></td>
            <td><a href="/KeibaWeb/TodayRaceInfo/DebaTable?k_babaCode=31&amp;k_raceDate=2026%2F11%2F15&amp;k_raceNo=1">架空</a></td>
            <td></td><td></td><td></td><td></td><td></td></tr>
            <tr class="data"><td>1R</td><td>2</td><td>架空馬</td><td>騎手変更</td><td>疾病</td><td>変更前→変更後</td></tr>
          </tbody></table></section></div>
        """)
        self.assertEqual(list(nar_racecard_links(page, date(2026, 11, 15), 31)), ['20261115-NAR-KOCHI-01'])

    def test_refresh_only_for_a_material_change(self):
        horse = {'horse_no': 1, 'status': 'DECLARED', 'jockey_name': '架空騎手', 'win_odds': 7.5}
        previous = {'runners': [horse], 'metadata': {'win_odds': {'1': 7.5}},
                    'off_at': '2026-11-15T15:40:00+09:00'}
        card = {'runners': [horse], 'off_at': '2026-11-15T06:40:00Z'}
        self.assertFalse(race_day_changes(previous, card))
        self.assertFalse(race_day_changes(previous, {**card, 'runners': [{**horse, 'win_odds': None}]}))
        self.assertTrue(race_day_changes(previous, {**card, 'runners': [{**horse, 'win_odds': 7.6}]}))
        self.assertTrue(race_day_changes(previous, {**card, 'runners': [{**horse, 'status': 'SCRATCHED'}]}))
        self.assertTrue(race_day_changes(previous, {**card, 'runners': [{**horse, 'body_weight': 480}]}))

    def test_batch_completion_counts_active_runners(self):
        card = {'runners': [{'status': 'DECLARED'}, {'status': 'SCRATCHED'}],
                'off_at': '2020-11-15T15:40:00+09:00'}
        roster_path = Path(__file__).resolve().parents[2] / 'data' / 'operations' / 'forecast_roster.json'
        from run_forecast_batch import read_json
        roster = read_json(roster_path)['forecasters']
        forecasts = [{'name': person['name'], 'execution_id': f'id-{index}', 'tickets': []}
                     for index, person in enumerate(roster)]
        value = {'race_id': '20261115-JRA-KYOTO-11', 'runners': 1, 'phase': 'FINAL',
                 'saved_at': '2020-11-14T12:00:00Z', 'forecasts': forecasts}
        validate_panel_output(value, value['race_id'], card, 'FINAL')
        with self.assertRaisesRegex(ValueError, 'runner count'):
            validate_panel_output({**value, 'runners': 2}, value['race_id'], card, 'FINAL')

    def test_archive_round_trip_preserves_bytes_and_refuses_a_conflict(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            history = root / 'history'
            verified = '20261115-JRA-KYOTO-11/v2.json'
            (history / verified).parent.mkdir(parents=True)
            (history / verified).write_bytes(b'{ "forecast":1 }\n')
            archive = root / 'run.zip'
            export_history(history, archive, {'phase': 'FINAL'})
            restored = root / 'restored'
            restored.mkdir()
            restore_history(restored, archive)
            self.assertEqual((restored / verified).read_bytes(), (history / verified).read_bytes())
            restore_history(restored, archive)
            conflict = root / 'other.zip'
            with ZipFile(conflict, 'w') as package:
                package.writestr('../outside/v2.json', '{}')
                package.writestr(verified, b'{}')
            with self.assertRaisesRegex(ValueError, 'disagrees'):
                restore_history(restored, conflict)
            self.assertFalse((root / 'outside').exists())
            self.assertEqual((restored / verified).read_bytes(), (history / verified).read_bytes())
