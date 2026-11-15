"""Read final horse-number payouts for a verified JRA or NAR race."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from unicodedata import normalize
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lxml import html
from fetch_jra_racecard import racecard_identity as jra_identity, read_jra
from fetch_nar_racecard import racecard_identity as nar_identity, VENUES
from jra_forecast_card import date_digits, nodes, number, text

TYPES = {'単勝': ('WIN', 1), '複勝': ('PLACE', 1), '馬連': ('QUINELLA', 2), '馬連複': ('QUINELLA', 2),
         '馬単': ('EXACTA', 2), '馬連単': ('EXACTA', 2), 'ワイド': ('WIDE', 2), '3連複': ('TRIO', 3),
         '三連複': ('TRIO', 3), '3連単': ('TRIFECTA', 3), '三連単': ('TRIFECTA', 3)}
REFUNDED = {'取消', '出走取消', '除外', '競走除外'}


def payout(label, legs, amount):
    kind, length = TYPES[label]
    if not re.fullmatch(r'\d{1,2}(?:\s*[-–]\s*\d{1,2})*', legs):
        raise ValueError(f'unreadable official {label} combination')
    numbers = [int(value) for value in re.findall(r'\d+', legs)]
    yen = number(amount.replace(',', ''), r'(\d+)\s*円')
    if len(numbers) != length or len(set(numbers)) != length or not yen or min(numbers) < 1:
        raise ValueError(f'invalid official {label} payout')
    return {'type': kind, 'horse_nos': numbers, 'payout_per_100_yen': yen}


def finish(position, horse_no, name):
    horse_no = number(normalize('NFKC', horse_no), r'(\d{1,2})')
    place = number(normalize('NFKC', position), r'(\d{1,2})(?:\s*(?:着|同着))?')
    if not horse_no or not name or place == 0 or not position:
        raise ValueError('incomplete official finisher identity')
    return {'horse_no': horse_no, 'horse_name': name, 'finish': place, 'status': position}


def parse_jra(page, identity):
    date, venue, venue_id, meeting, day, race = identity
    headers = nodes(page, 'race_header')
    if len(headers) != 1:
        raise ValueError('official JRA result header required')
    heading = text(headers[0], 'date')
    number_alt = headers[0].xpath('.//img[contains(@alt,"レース")]/@alt')
    if (date_digits(heading).replace('-', '') != date or f'{meeting}回{venue}{day}日' not in heading or
            f'{race}レース' not in number_alt):
        raise ValueError('JRA result header does not match requested race')
    tables = page.xpath('//table[thead//th[@class="place"] and thead//th[@class="horse"]]')
    units = nodes(page, 'refund_unit')
    if len(tables) != 1 or len(units) != 1:
        raise ValueError('final JRA finish and payout tables required')
    finishers = [finish(*(text(row, key) for key in ('place', 'num', 'horse')))
                 for row in tables[0].xpath('./tbody/tr[td]')]
    payouts = []
    for item in units[0].xpath('.//li[dl/dt]'):
        label = item.xpath('normalize-space(./dl/dt)')
        if label in TYPES:
            for line in nodes(item, 'line'):
                legs, amount = text(line, 'num'), text(line, 'yen')
                if legs in {'', '－', '-'} and amount in {'', '－', '-'}:
                    continue
                payouts.append(payout(label, legs, amount))
    return f'{date}-JRA-{venue_id}-{race:02d}', finishers, payouts


def parse_nar(page, identity):
    date, venue_code, race = identity
    venue, venue_id = VENUES[venue_code]
    headers = nodes(page, 'raceTitle')
    if len(headers) != 1:
        raise ValueError('official NAR result header required')
    headings = headers[0].getparent().xpath('./h4')
    heading = re.sub(r'\s+', '', text(headings[0])) if headings else ''
    if date_digits(heading) != date or f'{venue}第{race}競走競走成績' not in heading:
        raise ValueError('NAR result header does not match requested race')
    grades, dividends = nodes(page, 'gradeTable'), nodes(page, 'newRefundTable')
    if len(grades) != 1 or len(dividends) != 1:
        raise ValueError('final NAR finish and payout tables required')
    finishers = []
    for row in grades[0].xpath('./table/tbody/tr[td]|./tbody/tr[td]'):
        cells = row.xpath('./td')
        if len(cells) < 4:
            raise ValueError('incomplete NAR finisher row')
        finishers.append(finish(text(cells[0]), text(cells[2]), text(cells[3])))
    payouts = []
    for table in dividends[0].xpath('.//table'):
        label = None
        for row in table.xpath('./tbody/tr|./tr'):
            cells = row.xpath('./td')
            if not cells:
                continue
            if 'title' in (cells[0].get('class') or '').split():
                label = text(cells.pop(0))
            if label in TYPES:
                legs, amount = text(cells[0]), text(row, 'refundMoney')
                if legs in {'', '－', '-'} and amount in {'', '－', '-'}:
                    continue
                payouts.append(payout(label, legs, amount))
    return f'{date.replace("-", "")}-NAR-{venue_id}-{race:02d}', finishers, payouts


class NarResultRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        nar_identity(newurl, result=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, timeout=15):
    host = urlsplit(url).hostname
    if host in {'jra.go.jp', 'www.jra.go.jp'}:
        identity = jra_identity(url, result=True)
        final_url, raw, body = read_jra(url, timeout)
        if jra_identity(final_url, result=True) != identity:
            raise ValueError('JRA response changed result identity')
        race, finishers, payouts = parse_jra(html.fromstring(body), identity)
    else:
        identity = nar_identity(url, result=True)
        request = Request(url, headers={'User-Agent': 'PRISM-Racecard-Research/0.1 (official-source reader)'})
        with build_opener(NarResultRedirect).open(request, timeout=timeout) as response:
            final_url = response.geturl()
            if nar_identity(final_url, result=True) != identity:
                raise ValueError('NAR response changed result identity')
            raw = response.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError('result source too large')
        race, finishers, payouts = parse_nar(html.fromstring(raw.decode('utf-8-sig')), identity)
    return result_record(race, finishers, payouts, final_url, raw, datetime.now(timezone.utc).isoformat())


def result_record(race, finishers, payouts, url, raw, timestamp):
    if not finishers or len({row['horse_no'] for row in finishers}) != len(finishers):
        raise ValueError('complete unique official finisher list required')
    winners = {row['horse_no'] for row in finishers if row['finish'] == 1}
    win_payouts = [row['horse_nos'][0] for row in payouts if row['type'] == 'WIN']
    if not winners or len(winners) != len(win_payouts) or winners != set(win_payouts):
        raise ValueError('official win payouts do not match all first-place finishers')
    returned = {row['horse_no'] for row in finishers if row['status'] in REFUNDED}
    starting = {row['horse_no'] for row in finishers} - returned
    if any(not set(row['horse_nos']) <= starting for row in payouts):
        raise ValueError('official payout refers to a missing or refunded entrant')
    return {
        'schema': 'prism.official_result/v1', 'race_id': race, 'official_source': url,
        'source_sha256': sha256(raw).hexdigest(), 'published_at': timestamp,
        'published_at_basis': 'observed_at_collection', 'finishers': finishers, 'payouts': payouts,
        'refunded_horse_nos': sorted(returned), 'complete_payout_types': sorted({row['type'] for row in payouts}),
        'complete_payouts': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = fetch(args.url)
    with args.out.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
