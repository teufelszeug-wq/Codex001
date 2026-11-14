from pathlib import Path
import sys
import unittest

from lxml import html

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from fetch_official_result import parse_jra, parse_nar, result_record
from fetch_jra_racecard import racecard_identity as jra_identity
from fetch_nar_racecard import racecard_identity as nar_identity

JRA_URL = 'https://www.jra.go.jp/JRADB/accessS.html?CNAME=pw01sde1003202603021120261108/0A'
NAR_URL = 'https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_babaCode=27&k_raceDate=2026%2F11%2F13&k_raceNo=11'
JRA = """
<div class="race_header"><div class="date">2026年11月8日（日曜） 3回福島2日</div><img alt="11レース"></div>
<table><thead><tr><th class="place">着順</th><th class="horse">馬名</th></tr></thead><tbody>
<tr><td class="place">1</td><td class="num">2</td><td class="horse">架空馬甲</td></tr>
<tr><td class="place">1</td><td class="num">4</td><td class="horse">架空馬乙</td></tr>
<tr><td class="place">取消</td><td class="num">6</td><td class="horse">架空馬丙</td></tr>
</tbody></table>
<div class="refund_unit"><ul><li><dl><dt>単勝</dt><dd>
<div class="line"><div class="num">2</div><div class="yen">260円</div></div>
<div class="line"><div class="num">4</div><div class="yen">340円</div></div>
</dd></dl></li></ul></div>
"""
NAR = """
<div><h4>2026年11月13日（金） 園 田 第11競走 競走成績</h4><section class="raceTitle"></section></div>
<div class="gradeTable"><table><tbody>
<tr><td>1</td><td>2</td><td>2</td><td>架空馬甲</td></tr>
<tr><td>2</td><td>4</td><td>4</td><td>架空馬乙</td></tr>
</tbody></table></div>
<div class="newRefundTable"><table><tbody>
<tr><td class="title">単勝</td><td>2</td><td class="refundMoney">260円</td></tr>
<tr><td class="title" rowspan="2">複勝</td><td>2</td><td class="refundMoney">120円</td></tr>
<tr><td>4</td><td class="refundMoney">140円</td></tr>
</tbody></table></div>
"""


class OfficialResultTests(unittest.TestCase):
    def test_keeps_all_dead_heat_winners_and_scratch(self):
        race, finishers, payouts = parse_jra(html.fromstring(JRA), jra_identity(JRA_URL, result=True))
        result = result_record(race, finishers, payouts, JRA_URL, JRA.encode(), '2026-11-08T08:00:00Z')
        self.assertEqual(race, '20261108-JRA-FUKUSHIMA-11')
        self.assertEqual(result['refunded_horse_nos'], [6])
        self.assertEqual(result['complete_payout_types'], ['WIN'])
        self.assertEqual([row['horse_nos'] for row in result['payouts']], [[2], [4]])
        with self.assertRaisesRegex(ValueError, 'all first-place'):
            result_record(race, finishers, payouts[:-1], JRA_URL, JRA.encode(), '2026-11-08T08:00:00Z')

    def test_reads_nar_multirow_dividend_and_verifies_race(self):
        identity = nar_identity(NAR_URL, result=True)
        race, _, payouts = parse_nar(html.fromstring(NAR), identity)
        self.assertEqual(race, '20261113-NAR-SONODA-11')
        self.assertEqual([(row['type'], row['payout_per_100_yen']) for row in payouts],
                         [('WIN', 260), ('PLACE', 120), ('PLACE', 140)])
        with self.assertRaisesRegex(ValueError, 'does not match'):
            parse_nar(html.fromstring(NAR.replace('第11競走', '第10競走')), identity)
