"""Read pre-race facts from the official JRA racecard layout."""
from datetime import datetime, timedelta, timezone
import re

from lxml import html as lxml_html

JST = timezone(timedelta(hours=9))


def nodes(root, token, axis='.//'):
    return root.xpath(f'{axis}*[contains(concat(" ", normalize-space(@class), " "), $token)]',
                      token=f' {token} ')


def text(root, *tokens):
    for token in tokens:
        matches = nodes(root, token)
        if not matches:
            return ''
        root = matches[0]
    return ' '.join(root.text_content().split())


def number(value, pattern, convert=int):
    match = re.fullmatch(pattern, value)
    return convert(match[1]) if match else None


def date_digits(value):
    match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', value)
    if not match:
        raise ValueError('missing official date')
    year, month, day = (int(part) for part in match.groups())
    return datetime(year, month, day).date().isoformat()


def surface(value):
    if '障' in value or '障害' in value:
        return 'JUMP'
    if '芝' in value:
        return 'TURF'
    if 'ダ' in value:
        return 'DIRT'
    raise ValueError('unknown JRA surface')


def prior_start(cell, race_date):
    date = text(cell, 'date_line', 'date')
    if not date:
        return None
    date = date_digits(date)
    # A target-race line or a future race can never supply a PRE feature.
    if date >= race_date:
        raise ValueError('prior start is not before the target race date')
    distance = text(cell, 'dist')
    corners = nodes(cell, 'corner_list')
    running_positions = {}
    if corners:
        for item in corners[0].xpath('.//li'):
            position = number(text(item), r'(\d{1,2})')
            corner = number(item.get('title', ''), r'(\d)コーナー通過順位')
            if position is not None and corner is not None:
                running_positions[corner] = position
    return {
        'date': date,
        'venue': text(cell, 'date_line', 'rc') or None,
        'race_name': text(cell, 'race_line', 'name') or None,
        'surface': surface(distance) if distance else None,
        'distance_m': number(distance.replace(',', ''), r'(\d{3,4}).*'),
        'going': text(cell, 'condition') or None,
        'finish': number(text(cell, 'place'), r'(\d{1,2})着'),
        'field_size': number(text(cell, 'max'), r'(\d{1,2})頭'),
        'jockey_name': text(cell, 'info_line1', 'jockey') or None,
        'carried_weight': number(text(cell, 'info_line1', 'weight'), r'(\d+(?:\.\d+)?)\s*kg', float),
        'rating': number(text(cell, 'rating'), r'(\d{1,3})'),
        'last_3f': number(text(cell, 'f3'), r'3F\s*(\d{2}\.\d)', float),
        'first_call': next(iter(sorted(running_positions.items())), (None, None))[1],
        'fourth_corner': running_positions.get(4),
    }


def card_runners(table, race_date, allow_unframed=False):
    runners = []
    frame = None
    for row in table.xpath('./tbody/tr'):
        columns = {key: nodes(row, key, './') for key in ('waku', 'num', 'horse', 'jockey', 'past')}
        if not any(columns.values()):
            continue
        if not all(len(columns[key]) == 1 for key in ('num', 'horse', 'jockey')):
            raise ValueError('missing official runner columns')
        frame_explicit = False
        if columns['waku']:
            frame_cell = columns['waku'][0]
            alt = frame_cell.xpath('.//img/@alt')
            frame = number(alt[0] if alt else text(frame_cell), r'(?:枠)?([1-8]).*')
            frame_explicit = frame is not None
        horse = columns['horse'][0]
        jockey = columns['jockey'][0]
        horse_no = number(text(columns['num'][0]), r'(\d{1,2})')
        name = text(horse, 'name_line', 'name')
        if not name or horse_no is None and (not allow_unframed or text(columns['num'][0])):
            raise ValueError('missing official horse number or name')
        status_text = ' '.join((row.get('class', ''), text(horse, 'odds'), text(jockey, 'jockey')))
        if re.search(r'取消|cancel', status_text, re.IGNORECASE):
            status = 'SCRATCHED'
        elif re.search(r'除外|exclude', status_text, re.IGNORECASE):
            status = 'EXCLUDED'
        else:
            status = 'DECLARED'
        starts = [start for cell in columns['past'] if (start := prior_start(cell, race_date))]
        weight = re.search(r'(\d{3})\s*kg(?:[（(][+-]?\d+[)）])?', text(horse, 'result_line', 'weight'))
        horse_links = nodes(horse, 'name')
        hrefs = horse_links[0].xpath('.//a/@href') if horse_links else []
        horse_id = re.search(r'CNAME=pw01dud00(\d{10})/', hrefs[0]) if hrefs else None
        runners.append({
            'horse_no': horse_no,
            'horse_name': name,
            'horse_id': horse_id[1] if horse_id else None,
            'frame_no': frame,
            'status': status,
            'jockey_name': text(jockey, 'jockey') if status == 'DECLARED' else None,
            'carried_weight': number(text(jockey, 'weight'), r'(\d+(?:\.\d+)?)\s*kg', float),
            'official_rating': number(text(jockey, 'rating', 'num'), r'(\d{1,3})'),
            'body_weight': int(weight[1]) if weight else None,
            'win_odds': number(text(horse, 'odds', 'num'), r'(\d+(?:\.\d+)?)', float),
            'pedigree': {
                'sire': text(horse, 'sire').removeprefix('父：').strip() or None,
                'damsire': text(horse, 'bloodmare').removeprefix('(母の父：').rstrip(')').strip() or None,
            },
            'history': sorted(starts, key=lambda start: start['date'], reverse=True),
        })
        if horse_no is None and frame_explicit:
            raise ValueError('frame present without official horse number')
    if allow_unframed and runners and all(r['horse_no'] is None and r['frame_no'] is None for r in runners):
        identities = [r['horse_id'] for r in runners]
        if any(identity is None for identity in identities) or len(set(identities)) != len(identities) or len(runners) > 24:
            raise ValueError('unframed declarations require complete official horse IDs')
        return runners
    if any(r['horse_no'] is None for r in runners):
        raise ValueError('official runner numbers are incomplete')
    numbers = sorted(r['horse_no'] for r in runners)
    if not numbers or numbers != list(range(1, len(runners) + 1)) or len(runners) > 24:
        raise ValueError('official runner numbers are incomplete or duplicated')
    if any(r['frame_no'] is None for r in runners):
        raise ValueError('official frame numbers are missing')
    return sorted(runners, key=lambda runner: runner['horse_no'])


def parse_forecast_card(html, identity, captured_at, allow_unframed=False):
    page = lxml_html.fromstring(html)
    headers = nodes(page, 'race_header')
    if len(headers) != 1:
        raise ValueError('official JRA race header required')
    header = headers[0]
    expected_date, expected_venue, venue_id, expected_meeting, expected_day, expected_race = identity
    date_line = text(header, 'date')
    date = date_digits(date_line)
    meeting = re.search(r'(\d+)回(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)(\d+)日', date_line)
    race_number = nodes(header, 'race_number')
    race_number = race_number[0].xpath('.//img/@alt') if race_number else []
    race = number(race_number[0] if race_number else '', r'(\d{1,2})レース')
    if (date.replace('-', '') != expected_date or not meeting or
            (int(meeting[1]), meeting[2], int(meeting[3]), race) !=
            (expected_meeting, expected_venue, expected_day, expected_race)):
        raise ValueError('JRA race header does not match the requested race identity')
    clock = re.search(r'(\d{1,2})時(\d{2})分', text(header, 'time'))
    if not clock:
        raise ValueError('official post time required')
    off_at = datetime.fromisoformat(date).replace(hour=int(clock[1]), minute=int(clock[2]), tzinfo=JST)
    if captured_at.tzinfo is None or captured_at >= off_at:
        raise ValueError('official card must be captured before scheduled off')
    course = text(header, 'course')
    distance = re.search(r'([\d,]+)メートル', course.replace(' ', ''))
    name = text(header, 'race_name') or text(header, 'category')
    going = re.search(r'(?:芝|ダート)\s*(良|稍重|重|不良)', text(header, 'baba'))
    if not name or not distance:
        raise ValueError('official JRA race name or distance missing')
    tables = page.xpath('//table[thead//th[@class="waku"] and thead//th[@class="horse"]]')
    if len(tables) != 1:
        raise ValueError('official JRA runner table required')
    runners = card_runners(tables[0], date, allow_unframed)
    return {
        'schema': 'prism.official_racecard/v1',
        'authority': 'JRA',
        'race_id': f'{expected_date}-JRA-{venue_id}-{race:02d}',
        'race_name': name,
        'race_date': date,
        'venue': expected_venue,
        'race_no': race,
        'off_at': off_at.isoformat(),
        'captured_at': captured_at.isoformat(),
        'source_verified': True,
        'source_verification': 'JRA_RACECARD_IDENTITY_MATCH',
        'track_condition': going[1] if going else None,
        'course': {
            'surface': surface(course),
            'distance_m': int(distance[1].replace(',', '')),
            'direction': 'RIGHT' if '右' in course else 'LEFT' if '左' in course else 'STRAIGHT',
        },
        'runners': runners,
        **({'entry_stage': 'DECLARATIONS'} if runners[0]['horse_no'] is None else {}),
    }
