from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from fetch_jra_racecard import racecard_identity as jra_identity
from fetch_nar_racecard import parse_card as parse_nar, racecard_identity as nar_identity
from jra_forecast_card import parse_forecast_card as parse_jra

CAPTURED = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)
JRA_URL = 'https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202605041120261115/4C'
NAR_URL = 'https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/DebaTable?k_babaCode=32&k_raceDate=2026%2F11%2F14&k_raceNo=4'
JRA = """
<div class="race_header">
  <div class="date">2026年11月15日（日曜）5回京都4日</div><div class="time">15時40分</div>
  <div class="race_number"><img alt="11レース"></div><span class="race_name">架空特別</span>
  <div class="course">コース：2,200メートル（芝・右）</div>
</div>
<table><thead><tr><th class="waku">枠</th><th class="horse">馬名</th></tr></thead><tbody>
<tr><td class="waku" rowspan="2"><img alt="枠1白"></td><td class="num">1</td>
<td class="horse"><div class="name_line"><div class="name">架空馬甲</div><div class="odds"><span class="num">6.0</span></div></div></td>
<td class="jockey"><p class="jockey">架空騎手</p></td>
<td class="past p1"><div class="date_line"><span class="date">2026年10月11日</span><span class="rc">京都</span></div>
<div class="place">2着</div><span class="max">10頭</span><span class="dist">2200芝</span>
<div class="corner_list"><li title="4コーナー通過順位">3</li></div><div class="f3">3F 34.1</div></td></tr>
<tr class="cancel"><td class="num">2</td><td class="horse"><div class="name_line"><div class="name">架空馬乙</div></div></td>
<td class="jockey"></td></tr>
</tbody></table>
<table><thead><tr><th class="horse">無関係の表</th></tr></thead></table>
"""
NAR = """
<div><h4>2026年11月14日（土）　佐　賀　第4競走　17:00発走</h4>
<section class="raceTitle"><h3>架空特別</h3><ul class="dataArea"><li>ダート 1860ｍ（右）</li></ul></section></div>
<table><tbody><tr><td class="courseNum">1</td><td class="horseNum">1</td>
<td><a class="horseName" href="?k_lineageLoginCode=1234">架空馬</a></td>
<td><a class="jockeyName">架空騎手<span>（佐賀）</span></a></td><td class="odds_weight"></td>
<td>通算成績</td><td>2 26.11.01 稍重 11頭 佐賀 右1800 5番</td><td></td><td></td><td></td><td></td></tr>
<tr><td>牡6</td><td>鹿毛</td><td>03.09生</td><td>56.0</td><td>架空の前走</td><td></td><td></td><td></td><td></td></tr>
<tr><td>架空父</td><td>架空厩舎</td><td>3人 478 架空騎手 56.0</td><td></td><td></td><td></td><td></td></tr>
<tr><td>架空母</td><td>架空馬主</td><td>1:55.0 2-2-1-2 39.2</td><td></td><td></td><td></td><td></td></tr>
<tr><td>（架空母父）</td><td>架空牧場</td><td class="info"></td><td></td><td></td><td></td><td></td><td></td></tr></tbody></table>
<table class="sample"><tr><td class="horseNum">馬番</td></tr></table>
"""


class OfficialForecastCards(unittest.TestCase):
    def test_jra_uses_name_cell_and_carries_rowspan_frame(self):
        card = parse_jra(JRA, jra_identity(JRA_URL), CAPTURED)
        first, second = card['runners']
        self.assertEqual(card['race_id'], '20261115-JRA-KYOTO-11')
        self.assertEqual(first['horse_name'], '架空馬甲')
        self.assertEqual(first['win_odds'], 6.0)
        self.assertEqual(first['history'][0]['fourth_corner'], 3)
        self.assertEqual(second['frame_no'], 1)
        self.assertEqual(second['status'], 'SCRATCHED')

    def test_card_must_match_header_and_reject_target_history(self):
        with self.assertRaisesRegex(ValueError, 'does not match'):
            parse_jra(JRA.replace('5回京都4日', '5回東京4日'), jra_identity(JRA_URL), CAPTURED)
        with self.assertRaisesRegex(ValueError, 'prior start'):
            parse_jra(JRA.replace('2026年10月11日', '2026年11月15日'), jra_identity(JRA_URL), CAPTURED)

    def test_nar_ignores_sample_and_keeps_absent_odds(self):
        card = parse_nar(NAR.encode(), nar_identity(NAR_URL), CAPTURED)
        self.assertEqual(card['race_id'], '20261114-NAR-SAGA-04')
        first, = card['runners']
        self.assertEqual(first['horse_name'], '架空馬')
        self.assertIsNone(first['win_odds'])
        self.assertEqual(first['history'][0]['last_3f'], 39.2)
        self.assertEqual(first['history'][0]['jockey_name'], '架空騎手')

    def test_nar_blocks_post_off_and_mismatched_course(self):
        with self.assertRaisesRegex(ValueError, 'captured before'):
            parse_nar(NAR.encode(), nar_identity(NAR_URL), datetime(2026, 11, 14, 9, tzinfo=timezone.utc))
        with self.assertRaisesRegex(ValueError, 'does not match'):
            parse_nar(NAR.encode(), nar_identity(NAR_URL.replace('=32', '=31')), CAPTURED)


if __name__ == '__main__':
    unittest.main()
