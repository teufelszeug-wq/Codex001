"""Contract/error tests use labelled synthetic HTML, not live execution claims."""
from email.message import Message
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request

from prism_ops.official import (
    OfficialSourceError, _OfficialRedirect, fetch_official_snapshot,
    parse_jra_racecard, parse_nar_racecard, parse_nar_result,
    validate_official_url,
)


CARD_URL = "https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/DebaTable?k_babaCode=27&k_raceDate=2026%2F11%2F13&k_raceNo=11"
RESULT_URL = CARD_URL.replace("DebaTable", "RaceMarkTable")
HEADER = '<article class="raceCard">2026年11月13日(金) 園 田 第11競走 16:15発走</article><section class="raceTitle"><h3>試験特別</h3></section>'


def runner(number, name, *, frame=1, change=""):
    return f'<tr><td class="courseNum">{frame}</td><td class="horseNum">{number}</td><td><a class="horseName" href="/KeibaWeb/DataRoom/HorseMarkInfo?k_lineageLoginCode=3000000000{number}">{name}</a></td><td class="odds_weight">{change}</td></tr>'


CARD = HEADER + '<table>' + runner(1, "合成馬甲") + runner(2, "合成馬乙", frame=2) + '</table>'
PAYOUT = HEADER + '''<table><tbody>
<tr><td class="title" rowspan="1">単勝</td><td>1</td><td class="refundMoney">130円</td></tr>
<tr><td class="title" rowspan="2">複勝</td><td>1</td><td class="refundMoney">100円</td></tr>
<tr><td>2</td><td class="refundMoney">120円</td></tr>
<tr><td class="title">馬連単</td><td>2-1</td><td class="refundMoney">270円</td></tr>
</tbody></table>'''


class OfficialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def snapshot(self, text, url=CARD_URL, authority="NAR"):
        raw = text.encode("utf-8")
        path = self.directory / (hashlib.sha256(raw).hexdigest() + ".html")
        path.write_bytes(raw)
        return {"authority": authority, "official_url": url, "body_path": str(path),
                "captured_at": "2026-11-13T00:00:00Z", "source_sha256": hashlib.sha256(raw).hexdigest(),
                "encoding": "utf-8", "mode": "SYNTHETIC"}

    def card(self, text=CARD, **kwargs):
        return parse_nar_racecard(self.snapshot(text), expected_date="2026-11-13",
                                  expected_venue="27", expected_race_no=11, **kwargs)

    def result(self, text=PAYOUT):
        return parse_nar_result(self.snapshot(text, RESULT_URL), expected_date="2026-11-13",
                                expected_venue="27", expected_race_no=11)

    def test_exact_https_allowlist_and_pre_request_redirect(self):
        for url in ["http://www.keiba.go.jp/a", "https://keiba.go.jp.evil.test/a",
                    "https://user:pass@www.jra.go.jp/a", "https://www.jra.go.jp:444/a"]:
            with self.subTest(url=url), self.assertRaises(OfficialSourceError):
                validate_official_url(url)
        handler = _OfficialRedirect()
        with self.assertRaises(OfficialSourceError):
            handler.redirect_request(Request(CARD_URL), None, 302, "", {}, "https://evil.test/")

    def test_card_identity_names_ids_frames_and_fixture_status(self):
        card = self.card()
        self.assertEqual(card["race_id"], "NAR-20261113-27-11")
        self.assertEqual(card["start_at"], card["off_at"])
        self.assertEqual(card["declaration_stage"], "DRAW_CONFIRMED")
        self.assertEqual([h["horse_name"] for h in card["runners"]], ["合成馬甲", "合成馬乙"])
        self.assertEqual(card["runners"][1]["horse_id"], "30000000002")
        self.assertFalse(card["source_verified"])

    def test_wrong_page_identity_rejected_even_with_correct_url(self):
        with self.assertRaises(OfficialSourceError):
            self.card(CARD.replace("第11競走", "第10競走"))
        with self.assertRaises(OfficialSourceError):
            self.card(CARD.replace("園 田", "大 井"))
        with self.assertRaises(OfficialSourceError):
            parse_nar_racecard(self.snapshot(CARD), expected_date="2026-11-14", expected_venue=27, expected_race_no=11)

    def test_missing_changed_duplicate_runners_and_changed_bytes_rejected(self):
        for text in [CARD.replace('class="horseNum">2', 'class="unknown">2'),
                     CARD.replace('class="horseNum">2', 'class="horseNum">1'),
                     CARD.replace("30000000002", "30000000001")]:
            with self.subTest(text=text[-80:]), self.assertRaises(OfficialSourceError):
                self.card(text)
        s = self.snapshot(CARD)
        Path(s["body_path"]).write_text("changed", encoding="utf-8")
        with self.assertRaises(OfficialSourceError):
            parse_nar_racecard(s, expected_date="2026-11-13", expected_venue=27, expected_race_no=11)

    def test_current_cancel_excluded_without_mutating_original_snapshot(self):
        text = HEADER + '<table>' + runner(1, "合成馬甲", change="出走取消") + runner(2, "合成馬乙", frame=2) + '</table>'
        card = self.card(text)
        self.assertEqual(card["runners"][0]["status"], "SCRATCHED")
        self.assertEqual(len(card["active_runners"]), 1)
        self.assertEqual(card["active_runners"][0]["horse_no"], 2)

    def test_unpublished_results_fail_closed(self):
        with self.assertRaises(OfficialSourceError):
            self.result('<table class="cover_error"><tr><td>ご指定のレース成績の情報がありません</td></tr></table>')
        with self.assertRaises(OfficialSourceError):
            self.result(HEADER)

    def test_payout_rowspan_ordered_combinations_and_unknown_publication_time(self):
        result = self.result()
        self.assertIsNone(result["published_at"])
        self.assertEqual(result["publication_status"], "UNKNOWN_TIMESTAMP")
        self.assertEqual(result["first_observed_at"], result["source_snapshot"]["captured_at"])
        self.assertEqual(result["payouts"][-1]["horse_nos"], [2, 1])
        self.assertEqual(result["complete_bet_types"], ["EXACTA", "PLACE", "WIN"])
        self.assertTrue(result["complete_payouts"])
        self.assertEqual(len(result["source_snapshot"]["normalized_sha256"]), 64)

    def test_incomplete_payout_group_zero_amount_or_ambiguous_refund_rejected(self):
        for text in [PAYOUT.replace('rowspan="2"', 'rowspan="3"'), PAYOUT.replace("130円", "0円"),
                     PAYOUT.replace("130円", "返還")]:
            with self.subTest(text=text[-80:]), self.assertRaises(OfficialSourceError):
                self.result(text)
        result = self.result(PAYOUT + "出走取消")
        self.assertFalse(result["complete_payouts"])
        self.assertEqual(result["complete_bet_types"], [])

    def test_jra_thursday_declarations_do_not_invent_numbers(self):
        text = '''<h1>出馬表2026年11月14日 東京 11レース</h1><div class="race_header">合成競走 発走時刻:15時30分</div><table>
        <tr><td class="num"></td><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002022100001/">合成馬甲</a></td></tr>
        <tr><td class="num"></td><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002022100002/">合成馬乙</a></td></tr></table>'''
        s = self.snapshot(text, "https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0105202605031120261114/3E", "JRA")
        card = parse_jra_racecard(s, expected_date="2026-11-14", expected_venue="東京",
                                  expected_race_no=11, expected_race_name="合成競走")
        self.assertEqual(card["declaration_stage"], "ENTRIES_CONFIRMED")
        self.assertTrue(all(r["horse_no"] is None and r["frame_no"] is None for r in card["runners"]))
        with self.assertRaises(OfficialSourceError):
            parse_jra_racecard(s, expected_date="2026-11-14", expected_venue="京都",
                               expected_race_no=11, expected_race_name="合成競走")

    def test_jra_draw_uses_frame_image_and_excludes_non_selected_horses(self):
        text = '''<h1>出馬表2026年11月14日 東京 11レース</h1>
        <div class="race_header">合成競走 発走時刻:15時30分</div><table>
        <tr><td class="waku"><img src="/JRADB/img/waku/1.png"></td><td class="num">1</td><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002022100001/AA">合成馬甲</a></td></tr>
        <tr><td class="waku"><img src="/JRADB/img/waku/2.png"></td><td class="num">2</td><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002022100002/BB">合成馬乙</a></td></tr>
        </table><h2>非抽選馬情報</h2><table><tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002022100003/CC">合成非抽選馬</a></td></tr></table>'''
        s = self.snapshot(text, "https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0105202605031120261114/3E", "JRA")
        card = parse_jra_racecard(s, expected_date="2026-11-14", expected_venue="東京",
                                  expected_race_no=11, expected_race_name="合成競走")
        self.assertEqual(card["race_id"], "JRA-20261114-05-11")
        self.assertEqual(card["declaration_stage"], "DRAW_CONFIRMED")
        self.assertEqual(len(card["runners"]), 2)
        self.assertEqual([r["frame_no"] for r in card["runners"]], [1, 2])
        self.assertEqual([r["horse_no"] for r in card["runners"]], [1, 2])
        missing_id = self.snapshot(text.replace("pw01dud002022100001", "unknown"), s["official_url"], "JRA")
        with self.assertRaises(OfficialSourceError):
            parse_jra_racecard(missing_id, expected_date="2026-11-14", expected_venue="東京",
                               expected_race_no=11, expected_race_name="合成競走")

    def test_fetch_records_bytes_time_and_rejects_size_limit(self):
        class Response:
            status = 200
            headers = Message()
            headers["Content-Type"] = "text/html; charset=utf-8"
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return CARD_URL
            def read(self, n): return b"<html>synthetic</html>"[:n]
        class Opener:
            def open(self, *args, **kwargs): return Response()
        with patch("prism_ops.official.build_opener", return_value=Opener()):
            s = fetch_official_snapshot(CARD_URL, self.directory)
            self.assertEqual(Path(s["body_path"]).read_bytes(), b"<html>synthetic</html>")
            self.assertFalse(s["identity_verified"])
            with self.assertRaises(OfficialSourceError):
                fetch_official_snapshot(CARD_URL, self.directory, max_bytes=4)


if __name__ == "__main__":
    unittest.main()
