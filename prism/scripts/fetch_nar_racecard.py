"""Fetch and verify a numbered pre-race NAR racecard."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lxml import html as lxml_html
from jra_forecast_card import JST, nodes, number, text

VENUES = {
    3: ('帯広', 'OBIHIRO'), 4: ('旭川', 'ASAHIKAWA'), 5: ('門別', 'MONBETSU'),
    6: ('札幌', 'SAPPORO'), 10: ('盛岡', 'MORIOKA'), 11: ('水沢', 'MIZUSAWA'),
    18: ('浦和', 'URAWA'), 19: ('船橋', 'FUNABASHI'), 20: ('大井', 'OI'),
    21: ('川崎', 'KAWASAKI'), 22: ('金沢', 'KANAZAWA'), 23: ('笠松', 'KASAMATSU'),
    24: ('名古屋', 'NAGOYA'), 27: ('園田', 'SONODA'), 28: ('姫路', 'HIMEJI'),
    31: ('高知', 'KOCHI'), 32: ('佐賀', 'SAGA'),
}


def racecard_identity(url, *, result=False):
    parts = urlsplit(url)
    path = '/KeibaWeb/TodayRaceInfo/' + ('RaceMarkTable' if result else 'DebaTable')
    if (parts.scheme != 'https' or parts.hostname != 'www.keiba.go.jp'
            or parts.path != path
            or parts.username or parts.password or parts.port not in (None, 443)):
        raise ValueError('NAR official race result URL required' if result else 'NAR official numbered racecard URL required')
    query = parse_qs(parts.query)
    values = [query.get(key, []) for key in ('k_raceDate', 'k_babaCode', 'k_raceNo')]
    if any(len(value) != 1 for value in values):
        raise ValueError('NAR race identity is missing')
    date = datetime.strptime(values[0][0], '%Y/%m/%d').date().isoformat()
    code, race_no = (int(value[0]) for value in values[1:])
    if code not in VENUES or not 1 <= race_no <= 12:
        raise ValueError('invalid NAR race identity')
    return date, code, race_no


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        racecard_identity(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_past(label, name, rider, timing, date, surface):
    line = re.match(r'(?:(\d{1,2})\s+)?(\d{2}\.\d{2}\.\d{2})\s+(\S+)\s+(\d{1,2})頭\s+(\S+)\s+[左右直](\d{3,4})', label)
    if not line:
        return None
    day = datetime.strptime(line[2], '%y.%m.%d').date().isoformat()
    if day >= date:
        raise ValueError('prior start is not before the target race date')
    corners = re.search(r' (\d{1,2}(?:-\d{1,2})+) ', timing)
    positions = [int(part) for part in corners[1].split('-')] if corners else []
    jockey = re.search(r'([\w.・]+)\s+\d+(?:\.\d+)?$', rider)
    return {
        'date': day, 'venue': line[5], 'race_name': name, 'surface': surface, 'distance_m': int(line[6]),
        'going': line[3], 'finish': int(line[1]) if line[1] else None, 'field_size': int(line[4]),
        'jockey_name': jockey[1] if jockey else None, 'carried_weight': None, 'rating': None,
        'last_3f': number(timing, r'.+\s(\d{2}\.\d)', float),
        'first_call': positions[0] if positions else None,
        'fourth_corner': positions[3] if len(positions) == 4 else None,
    }


def parse_runners(page, date, surface):
    tables = page.xpath('//table[not(contains(concat(" ", normalize-space(@class), " "), " sample "))'
                        ' and (./tr/td[@class="horseNum"] or ./tbody/tr/td[@class="horseNum"])]')
    if len(tables) != 1:
        raise ValueError('official NAR runner table required')
    rows = tables[0].xpath('./tr|./tbody/tr')
    runners, frame = [], None
    for index, row in enumerate(rows):
        horse_cell = nodes(row, 'horseNum', './')
        if not horse_cell:
            continue
        frame_cell = nodes(row, 'courseNum', './')
        if frame_cell:
            frame = number(text(frame_cell[0]), r'([1-8])')
        horse_no = number(text(horse_cell[0]), r'(\d{1,2})')
        links = nodes(row, 'horseName')
        name = text(links[0]) if links else ''
        if not name or horse_no is None or frame is None or len(rows) < index + 5:
            raise ValueError('incomplete official NAR runner row')
        horse_id = re.search(r'k_lineageLoginCode=(\d+)', links[0].get('href', ''))
        jockey_links = nodes(row, 'jockeyName')
        jockey = ' '.join(''.join(jockey_links[0].xpath('./text()')).split()) if jockey_links else None
        parts = [row.xpath('./td') for row in rows[index:index + 5]]
        status_text = ' '.join(text(cell) for line in parts for cell in line if 'odds_weight' in cell.get('class', '') or 'info' in cell.get('class', '').split())
        status = 'SCRATCHED' if '取消' in status_text else 'EXCLUDED' if '除外' in status_text else 'DECLARED'
        odds = re.match(r'(\d+(?:\.\d+)?)\b', text(row, 'odds_weight'))
        win_odds = float(odds[1]) if odds else None
        weigh_in = [text(cell) for cell in parts[2] if 'odds_weight' in cell.get('class', '').split()]
        body_weight = number(weigh_in[0], r'(\d{3})\s*(?:[（(][+-]?\d+[)）])?') if weigh_in else None
        history = []
        if all(len(line) >= 5 for line in parts[:4]):
            for cells in zip(*(line[-5:] for line in parts[:4])):
                if start := parse_past(*(text(cell) for cell in cells), date, surface):
                    history.append(start)
        runners.append({
            'horse_no': horse_no, 'horse_name': name, 'horse_id': horse_id[1] if horse_id else None,
            'frame_no': frame, 'status': status, 'jockey_name': jockey,
            'carried_weight': None, 'official_rating': None, 'win_odds': win_odds if win_odds and win_odds >= 1 else None,
            'body_weight': body_weight,
            'pedigree': {
                'sire': text(parts[2][0]) or None,
                'damsire': text(parts[4][0]).strip('（）()') or None,
            },
            'history': sorted(history, key=lambda start: start['date'], reverse=True),
        })
    numbers = sorted(runner['horse_no'] for runner in runners)
    if not numbers or numbers != list(range(1, len(runners) + 1)) or len(runners) > 24:
        raise ValueError('official NAR runner numbers are incomplete or duplicated')
    return sorted(runners, key=lambda runner: runner['horse_no'])


def parse_card(body, identity, captured_at):
    page = lxml_html.fromstring(body.decode('utf-8-sig'))
    date, venue_code, race_no = identity
    venue, venue_id = VENUES[venue_code]
    titles = nodes(page, 'raceTitle')
    if len(titles) != 1:
        raise ValueError('official NAR race header required')
    title = titles[0]
    headers = title.getparent().xpath('./h4')
    heading = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日\([^)]+\)(.+?)第(\d{1,2})競走(\d{1,2}):(\d{2})発走',
                        re.sub(r'\s+', '', text(headers[0])).replace('（', '(').replace('）', ')') if headers else '')
    if not heading or heading[4] != venue or int(heading[5]) != race_no:
        raise ValueError('NAR race header does not match the requested race identity')
    year, month, day = (int(part) for part in heading.groups()[:3])
    off_at = datetime(year, month, day, int(heading[6]), int(heading[7]), tzinfo=JST)
    if off_at.date().isoformat() != date or captured_at.tzinfo is None or captured_at >= off_at:
        raise ValueError('official card must match the race date and be captured before scheduled off')
    race_name = title.xpath('normalize-space(./h3)')
    course_text = text(title, 'dataArea')
    distance = re.search(r'(\d{3,4})\s*[ｍm]', course_text)
    if not race_name or not distance:
        raise ValueError('official NAR race name or distance missing')
    surface = 'BANEI' if venue_code == 3 else 'TURF' if '芝' in course_text else 'DIRT'
    going = re.search(r'馬場[：:]\s*([\d.]+|良|稍重|重|不良)', course_text)
    return {
        'schema': 'prism.official_racecard/v1', 'authority': 'NAR',
        'race_id': f'{date.replace("-", "")}-NAR-{venue_id}-{race_no:02d}', 'race_name': race_name,
        'race_date': date, 'venue': venue, 'race_no': race_no, 'off_at': off_at.isoformat(),
        'captured_at': captured_at.isoformat(), 'source_verified': True,
        'source_verification': 'NAR_RACECARD_IDENTITY_MATCH',
        'course': {
            'surface': surface, 'distance_m': int(distance[1]),
            'direction': 'RIGHT' if '右' in course_text else 'LEFT' if '左' in course_text else 'STRAIGHT',
        },
        'track_condition': going[1] if going else None,
        'runners': parse_runners(page, date, surface),
    }


def fetch_for_forecast(url, timeout=15):
    identity = racecard_identity(url)
    request = Request(url, headers={'User-Agent': 'PRISM-Racecard-Research/0.1 (official-source reader)'})
    with build_opener(OfficialRedirect).open(request, timeout=timeout) as response:
        final_url = response.geturl()
        if racecard_identity(final_url) != identity:
            raise ValueError('NAR response changed race identity')
        body = response.read(3_000_001)
    if len(body) > 3_000_000:
        raise ValueError('source too large')
    card = parse_card(body, identity, datetime.now(timezone.utc))
    return {**card, 'official_url': final_url, 'source_sha256': sha256(body).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    card = fetch_for_forecast(args.url)
    with Path(args.out).open('x', encoding='utf-8') as target:
        json.dump(card, target, ensure_ascii=False, indent=2)
        target.write('\n')
    print(json.dumps({'race_id': card['race_id'], 'runners': len(card['runners']), 'captured_at': card['captured_at']}))


if __name__ == '__main__':
    main()
