"""Official navigation discovery with retained source bytes and explicit gaps.

Adapted selectively from PR #12 discover_official_races.py (18ba748). Discovered
links identify retrieval candidates, never completed forecasts or verified cards.
Every network read uses fetch_official_snapshot; injected readers stay synthetic.
Only the known JRA index and retained doAction menus use POST navigation.
Unsupported selections remain errors, never guessed JRA checksums.
"""
from copy import deepcopy
from datetime import date
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from .official import (JRA_VENUES, NAR_VENUES, OfficialSourceError, _class, _document,
                       _text, fetch_official_snapshot, jra_url_identity,
                       validate_official_url)

JRA = 'https://www.jra.go.jp'
NAR = 'https://www.keiba.go.jp'


def _days(dates):
    values = sorted({date.fromisoformat(str(value)) for value in dates})
    if not values:
        raise OfficialSourceError('at least one explicit discovery date required')
    return values


def _record(identity, url, snapshot, *, endpoint='RACECARD'):
    return {**identity, 'authority': snapshot['authority'], 'official_url': url,
            'endpoint': endpoint, 'source_snapshot': deepcopy(snapshot),
            'discovery_status': 'OFFICIAL_LINK_NOT_PARSED_RACECARD',
            'official_input_verified': False}


def parse_jra_navigation(snapshot, *, dates, result=False):
    root = _document(snapshot, 'JRA')
    days = {d.isoformat() for d in _days(dates)}
    path = '/JRADB/accessS.html' if result else '/JRADB/accessD.html'
    area = root.xpath('//*[@id="contentsBody"]')
    area = area[0] if len(area) == 1 else root
    candidates, menus = {}, {}
    links = []
    # A selected card may omit its own URL from the navigation.
    try:
        selected = jra_url_identity(snapshot['official_url'], result=result)
    except OfficialSourceError:
        pass
    else:
        if selected['race_date'] in days:
            links.append(snapshot['official_url'])
    for node in area.xpath('.//a[@href or @onclick]'):
        href = urljoin(snapshot['official_url'], node.get('href', ''))
        action = re.search(r"doAction\(\s*'([^']+)'\s*,\s*'([^']+)'", node.get('onclick', ''))
        if action and action[1] == path:
            href = JRA + path + '?' + urlencode({'CNAME': action[2]})
        parts = urlsplit(href)
        if (parts.scheme != 'https' or parts.fragment or
                parts.hostname not in ('www.jra.go.jp', 'jra.go.jp') or parts.path != path):
            continue
        validate_official_url(href, 'JRA')
        codes = parse_qs(parts.query).get('CNAME', [])
        if len(codes) != 1:
            continue
        try:
            identity = jra_url_identity(href, result=result)
        except OfficialSourceError:
            menu = re.fullmatch(r'pw01[sd]rl(?:00|01|10)\d{18}/[0-9A-Fa-f]{2}', codes[0])
            if menu and codes[0][-11:-3] in {d.replace('-', '') for d in days}:
                menus[href] = {'official_url': href, 'source_snapshot': deepcopy(snapshot),
                               'form_navigation_observed': bool(action)}
            continue
        if identity['race_date'] in days:
            links.append(href)
    for url in links:
        identity = jra_url_identity(url, result=result)
        candidate = _record(identity, url, snapshot, endpoint='RESULT' if result else 'RACECARD')
        previous = candidates.get(identity['race_id'])
        # 01/10 result aliases are both published and identify the same race.
        if previous is None:
            candidates[identity['race_id']] = candidate
    if not candidates and not menus:
        raise OfficialSourceError('no published JRA navigation links; form-only or changed layout remains unverified')
    return {'candidates': list(candidates.values()), 'menus': list(menus.values())}


def _nar_url_identity(url, *, endpoint):
    validate_official_url(url, 'NAR')
    parts, values = urlsplit(url), parse_qs(urlsplit(url).query)
    if not parts.path.endswith('/' + endpoint):
        raise OfficialSourceError('official NAR navigation endpoint mismatch')
    required = ('k_raceDate', 'k_babaCode') + (('k_raceNo',) if endpoint != 'RaceList' else ())
    if any(len(values.get(key, [])) != 1 for key in required):
        raise OfficialSourceError('explicit NAR navigation identity required')
    try:
        day = date.fromisoformat(values['k_raceDate'][0].replace('/', '-'))
        venue = str(int(values['k_babaCode'][0])).zfill(2)
        race_no = int(values['k_raceNo'][0]) if endpoint != 'RaceList' else None
    except (ValueError, TypeError) as exc:
        raise OfficialSourceError('invalid NAR navigation date or number') from exc
    if venue not in NAR_VENUES or race_no is not None and not 1 <= race_no <= 12:
        raise OfficialSourceError('unknown NAR navigation venue or race')
    return {'race_date': day.isoformat(), 'venue_code': venue, 'venue_name': NAR_VENUES[venue],
            **({'race_id': f'NAR-{day:%Y%m%d}-{venue}-{race_no:02d}', 'race_no': race_no} if race_no is not None else {})}


def parse_nar_calendar(snapshot, *, expected_date):
    root = _document(snapshot, 'NAR')
    day = date.fromisoformat(str(expected_date))
    parts = urlsplit(snapshot['official_url'])
    if parts.path != '/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop':
        raise OfficialSourceError('official NAR calendar endpoint required')
    query = parse_qs(parts.query)
    selected = root.xpath('//select[@name="k_year"]/option[@selected]/@value')
    active = root.xpath(f'//*[@id="monthTab{day.month}" and {_class("active")}]')
    if (query.get('k_year') != [str(day.year)] or query.get('k_month') != [str(day.month)] or
            selected != [str(day.year)] or not active):
        raise OfficialSourceError('official NAR calendar selection changed')
    schedules = root.xpath('//*[' + _class('schedule') + ']')
    if len(schedules) != 1:
        raise OfficialSourceError('official NAR monthly calendar missing')
    by_name = {name: code for code, name in NAR_VENUES.items()}
    menus, gaps = {}, []
    for row in schedules[0].xpath('.//tr[td and not(th)]'):
        cells = row.xpath('./td')
        if len(cells) <= day.day or not _text(cells[day.day]):
            continue
        name = re.sub(r'\s+', '', _text(cells[0])).removesuffix('競馬').removesuffix('ば')
        if name not in by_name:
            if cells[day.day].xpath('.//a[@href]'):
                gaps.append({'code': 'UNKNOWN_NAR_CALENDAR_VENUE', 'detail': name})
            continue
        links = cells[day.day].xpath('.//a[contains(@href,"RaceList")]/@href')
        if len(links) != 1:
            gaps.append({'code': 'NAR_MENU_LINK_UNAVAILABLE', 'detail': name})
            continue
        url = urljoin(snapshot['official_url'], links[0])
        identity = _nar_url_identity(url, endpoint='RaceList')
        if identity['race_date'] != day.isoformat() or identity['venue_code'] != by_name[name]:
            raise OfficialSourceError('NAR calendar links to a different date or venue')
        menus[url] = {'official_url': url, **identity, 'source_snapshot': deepcopy(snapshot)}
    return {'menus': list(menus.values()), 'errors': gaps}


def parse_nar_navigation(snapshot, *, expected_date, expected_venue):
    root = _document(snapshot, 'NAR')
    identity = _nar_url_identity(snapshot['official_url'], endpoint='RaceList')
    code = str(expected_venue).zfill(2)
    day = date.fromisoformat(str(expected_date))
    if identity['race_date'] != day.isoformat() or identity['venue_code'] != code:
        raise OfficialSourceError('NAR menu URL selection changed')
    tables = root.xpath('//*[' + _class('raceTable') + ']')
    if len(tables) != 1:
        raise OfficialSourceError('official NAR race menu missing')
    headings = tables[0].xpath('.//th[@colspan][1]')
    text = _text(headings[0]) if headings else ''
    if (not re.search(rf'{day.year}年\s*{day.month}月\s*{day.day}日', text) or
            identity['venue_name'] not in re.sub(r'\s+', '', text)):
        raise OfficialSourceError('NAR race menu header selection changed')
    candidates = {}
    for row in tables[0].xpath('.//tr[' + _class('data') + ']'):
        cells = row.xpath('./td')
        if len(cells) != 10:
            continue  # The separate runner-change table is not a race list.
        number = re.fullmatch(r'(\d{1,2})R', _text(cells[0]))
        links = row.xpath('.//a[contains(@href,"/DebaTable?")]/@href')
        if not number or len(links) != 1:
            raise OfficialSourceError('NAR race slot has no unambiguous published card link')
        url = urljoin(snapshot['official_url'], links[0])
        linked = _nar_url_identity(url, endpoint='DebaTable')
        if (linked['race_date'] != day.isoformat() or linked['venue_code'] != code or
                linked['race_no'] != int(number[1]) or linked['race_id'] in candidates):
            raise OfficialSourceError('NAR menu has duplicate or mismatched race identity')
        candidates[linked['race_id']] = _record(linked, url, snapshot)
    if not candidates:
        raise OfficialSourceError('NAR menu contains no published racecards')
    return list(candidates.values())


def discover_official_races(authority, dates, evidence_dir, *, seeds=(), result=False,
                            fetcher=None, max_pages=80):
    """Return candidates plus source-backed gaps; never upgrade counts to VERIFIED.

    NAR discovery returns card links. Its result URLs must be read/normalized by
    the result parser before settlement; no result is inferred from a menu.
    """
    days = _days(dates)
    if authority not in ('JRA', 'NAR') or type(max_pages) is not int or max_pages < 1:
        raise ValueError('authority and positive page budget required')
    if authority == 'NAR' and result:
        raise ValueError('NAR result discovery requires explicit result URLs; discover its card catalog first')
    fetch = fetcher or fetch_official_snapshot
    candidates, snapshots, errors, seen, queue, observed_forms = {}, [], [], set(), [], {}
    def read(url):
        validate_official_url(url, authority)
        options = {}
        if authority == 'JRA':
            code = parse_qs(urlsplit(url).query).get('CNAME', [])
            if len(code) == 1 and code[0] in ('pw01dli00/F3', 'pw01sli00/AF'):
                options['form_cname'] = code[0]
            elif url in observed_forms:
                options.update(form_cname=code[0], navigation_snapshot=observed_forms[url])
        snapshot = deepcopy(fetch(url, evidence_dir, **options))
        if fetcher is not None:
            snapshot.update(mode='SYNTHETIC', identity_verified=False)
        if snapshot.get('authority') != authority:
            raise OfficialSourceError('discovery source authority mismatch')
        snapshots.append(snapshot)
        return snapshot
    if authority == 'JRA':
        route, index = ('S', 'pw01sli00/AF') if result else ('D', 'pw01dli00/F3')
        queue = [*seeds, JRA + '/JRADB/access' + route + '.html?' + urlencode({'CNAME': index})]
    else:
        queue = [*seeds, *[NAR + '/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop?' +
                 urlencode({'k_year': y, 'k_month': m}) for y, m in sorted({(d.year, d.month) for d in days})]]
    while queue and len(seen) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            snapshot = read(url)
            if authority == 'JRA':
                parsed = parse_jra_navigation(snapshot, dates=days, result=result)
                for candidate in parsed['candidates']:
                    candidates.setdefault(candidate['race_id'], candidate)
                for menu in parsed['menus']:
                    if menu['form_navigation_observed']:
                        observed_forms[menu['official_url']] = menu['source_snapshot']
                    if menu['official_url'] not in seen:
                        queue.append(menu['official_url'])
                # A numbered card exposes all remaining races at its venue.
                meetings = {(r['race_date'], r['venue_code']) for r in candidates.values()}
                for meeting in meetings:
                    rows = [r for r in candidates.values() if (r['race_date'], r['venue_code']) == meeting]
                    if len(rows) < 12:
                        queue.extend(r['official_url'] for r in sorted(rows, key=lambda r: r['race_no'] != 11)
                                     if r['official_url'] not in seen)
            elif 'MonthlyConveneInfoTop' in urlsplit(url).path:
                for day in days:
                    if (parse_qs(urlsplit(url).query).get('k_month') == [str(day.month)] and
                            parse_qs(urlsplit(url).query).get('k_year') == [str(day.year)]):
                        parsed = parse_nar_calendar(snapshot, expected_date=day)
                        errors.extend(parsed['errors'])
                        queue.extend(row['official_url'] for row in parsed['menus'])
            else:
                identity = _nar_url_identity(url, endpoint='RaceList')
                for candidate in parse_nar_navigation(snapshot, expected_date=identity['race_date'], expected_venue=identity['venue_code']):
                    candidates.setdefault(candidate['race_id'], candidate)
        except (OSError, ValueError, KeyError) as exc:
            errors.append({'code': 'UNVERIFIED_OFFICIAL_DISCOVERY', 'official_url': url,
                           'detail': str(exc)[:300]})
    if set(queue) - seen:
        errors.append({'code': 'DISCOVERY_PAGE_BUDGET_EXHAUSTED', 'remaining_links': len(set(queue) - seen)})
    if authority == 'JRA' and not result:
        for day, venue in sorted({(r['race_date'], r['venue_code']) for r in candidates.values()}):
            count = sum(r['race_date'] == day and r['venue_code'] == venue for r in candidates.values())
            if count != 12:
                errors.append({'code': 'JRA_RACE_SLOTS_INCOMPLETE', 'race_date': day,
                               'venue_code': venue, 'observed_slots': count})
    observed_days = {r['race_date'] for r in candidates.values()}
    for day in days:
        if day.isoformat() not in observed_days:
            errors.append({'code': 'NO_CONFIRMED_RACE_LINKS', 'race_date': day.isoformat()})
    return {'schema': 'prism.official_discovery/v1', 'authority': authority,
            'dates': [d.isoformat() for d in days], 'candidate_count': len(candidates),
            'candidates': [candidates[k] for k in sorted(candidates)], 'errors': errors,
            'source_snapshots': snapshots, 'status': 'INCOMPLETE' if errors else 'DISCOVERED_LINKS_ONLY',
            'official_input_verified': False, 'verified_forecasts': 0}
