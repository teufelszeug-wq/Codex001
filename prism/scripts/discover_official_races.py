"""Discover race URLs from the official JRA navigation and NAR calendar."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from lxml import html

from fetch_jra_racecard import racecard_identity as jra_identity, read_jra
from fetch_nar_racecard import VENUES, racecard_identity as nar_identity
from jra_forecast_card import date_digits, nodes, text

JRA = 'https://www.jra.go.jp'
NAR = 'https://www.keiba.go.jp'
NAR_DAY = '/KeibaWeb/TodayRaceInfo/'
NAR_CALENDAR = '/KeibaWeb/MonthlyConveneInfo/MonthlyConveneInfoTop'


def jra_url(path, code):
    return JRA + path + '?' + urlencode({'CNAME': code})


def jra_links(page, *, result=False):
    path = '/JRADB/accessS.html' if result else '/JRADB/accessD.html'
    menu_pattern = r'pw01[sd]rl(?:00|01|10)\d{18}/[0-9A-F]{2}'
    # Use the navigation outside the past-performance table.
    root = page.xpath('//*[@id="contentsBody"]')
    root = root[0] if root else page
    for node in root.xpath('.//a[@href or @onclick]'):
        href = urlsplit(urljoin(JRA, node.get('href', '')))
        codes = parse_qs(href.query).get('CNAME', []) if href.hostname in {'www.jra.go.jp', 'jra.go.jp'} and href.path == path else []
        action = re.search(r"doAction\(\s*'([^']+)'\s*,\s*'([^']+)'", node.get('onclick', ''))
        if action and action[1] == path:
            codes.append(action[2])
        for code in codes:
            url = jra_url(path, code)
            try:
                day, _, venue, _, _, race = jra_identity(url, result=result)
            except ValueError:
                if re.fullmatch(menu_pattern, code):
                    yield (code[-11:-3], None, None), url, bool(action)
            else:
                yield (day, venue, race), url, False


def jra_page(url, use_form=False):
    if use_form:
        parts = urlsplit(url)
        code = parse_qs(parts.query)['CNAME'][0]
        _, _, body = read_jra(JRA + parts.path, form_code=code)
    else:
        _, _, body = read_jra(url)
    return html.fromstring(body)


def jra_index(url):
    try:
        return jra_page(url, True)
    except (OSError, ValueError):
        return jra_page(url)


def discover_jra(days, seeds=(), *, result=False):
    targets = {day.strftime('%Y%m%d') for day in days}
    index = jra_url('/JRADB/accessS.html', 'pw01sli00/AF') if result else jra_url('/JRADB/accessD.html', 'pw01dli00/F3')
    urls, menus, seen, errors = {}, {}, set(), []

    def read(url, loader):
        seen.add(url)
        try:
            page = loader(url)
            # The selected card can omit its own URL from the navigation.
            try:
                day, _, venue, _, _, race = jra_identity(url, result=result)
            except ValueError:
                pass
            else:
                if day in targets:
                    urls[(day, venue, race)] = url
            for key, linked, form in jra_links(page, result=result):
                if key[0] in targets:
                    if key[1] is None:
                        menus.setdefault(linked, form)
                    else:
                        urls.setdefault(key, linked)
            return True
        except (OSError, ValueError) as error:
            errors.append(f'{url}: {error}')
            return False

    for seed in dict.fromkeys(seeds):
        jra_identity(seed, result=result)
        read(seed, jra_page)
    # The index is required to find newly published dates absent from the saved-day seeds.
    if targets - {key[0] for key in urls} or not urls:
        read(index, jra_index)
    for url, use_form in list(menus.items()):
        code = parse_qs(urlsplit(url).query)['CNAME'][0]
        if url not in seen and code[-11:-3] not in {key[0] for key in urls}:
            read(url, jra_index if use_form else jra_page)
    # Navigation within one numbered race exposes the remaining races at that venue.
    meetings = {}
    for (day, venue, race), url in urls.items():
        meetings.setdefault((day, venue), []).append((race, url))
    for rows in meetings.values():
        if len(rows) < 12:
            choices = sorted(rows, key=lambda row: row[0] != 11)
            remaining = [url for _, url in choices if url not in seen]
            for url in remaining:
                if read(url, jra_page):
                    break
    if not result:
        for day, venue in meetings:
            if sum(key[:2] == (day, venue) for key in urls) != 12:
                errors.append(f'{day}-JRA-{venue}: official navigation did not list all 12 race slots')
    return {f'{day}-JRA-{venue}-{race:02d}': url for (day, venue, race), url in sorted(urls.items())}, errors


def check_nar_host(url):
    parts = urlsplit(url)
    if (parts.scheme, parts.hostname) != ('https', 'www.keiba.go.jp') or parts.username or parts.password or parts.port:
        raise ValueError('official NAR HTTPS URL required')
    return parts


class NarRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_nar_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def nar_page(url):
    initial = check_nar_host(url)
    request = Request(url, headers={'User-Agent': 'PRISM-Racecard-Research/0.1 (official-source reader)'})
    with build_opener(NarRedirect).open(request, timeout=15) as response:
        final = check_nar_host(response.geturl())
        if final.path != initial.path or parse_qs(final.query) != parse_qs(initial.query):
            raise ValueError('NAR menu redirected to a different selection')
        body = response.read(3_000_001)
    if len(body) > 3_000_000:
        raise ValueError('NAR menu too large')
    return html.fromstring(body.decode('utf-8-sig'))


def nar_meetings(page, day):
    tables = nodes(page, 'schedule')
    if len(tables) != 1:
        raise ValueError('official NAR monthly calendar missing')
    fields = {select.get('name'): select.xpath('option[@selected]/@value')
              for select in page.xpath('//select[@name]')}
    if fields.get('k_year') != [str(day.year)] or not page.xpath(f'//*[@id="monthTab{day.month}" and contains(concat(" ", normalize-space(@class), " "), " active ")]'):
        raise ValueError('NAR calendar month changed')
    venues = {name: code for code, (name, _) in VENUES.items()}
    meetings = {}
    for row in tables[0].xpath('.//tr[td and not(th)]'):
        cells = row.xpath('./td')
        if len(cells) <= day.day or not text(cells[day.day]):
            continue
        venue = text(cells[0]).removesuffix('ば')
        if venue not in venues:
            if cells[day.day].xpath('.//a[contains(@href,"RaceList")]'):
                raise ValueError(f'unknown official NAR venue: {venue}')
            continue
        code = venues[venue]
        meetings[code] = NAR + NAR_DAY + 'RaceList?' + urlencode({'k_babaCode': code, 'k_raceDate': day.strftime('%Y/%m/%d')})
    return meetings


def nar_racecard_links(page, day, code):
    venue, venue_id = VENUES[code]
    table = nodes(page, 'raceTable')
    if len(table) != 1:
        raise ValueError('NAR race menu is not published')
    heading = table[0].xpath('.//th[@colspan][1]')
    if not heading or date_digits(text(heading[0])) != day.isoformat() or f'{venue}競馬' not in text(heading[0]).replace('ば競馬', '競馬'):
        raise ValueError('NAR race menu date or venue changed')
    races = {}
    for row in table[0].xpath('./table/tbody/tr|./table/tr'):
        if 'data' not in (row.get('class') or '').split():
            continue
        cells = row.xpath('./td')
        if len(cells) != 10:
            continue  # Runner changes are listed in a second block of this table.
        match = re.fullmatch(r'(\d{1,2})R', text(cells[0]))
        if not match:
            raise ValueError('NAR race slot number missing')
        links = row.xpath('.//a[contains(@href,"/DebaTable?")]/@href')
        if len(links) != 1:
            raise ValueError(f'NAR race {match[1]} has no published racecard')
        url = urljoin(NAR, links[0])
        if nar_identity(url) != (day.isoformat(), code, int(match[1])):
            raise ValueError('NAR menu links to a different race')
        races[f'{day:%Y%m%d}-NAR-{venue_id}-{int(match[1]):02d}'] = url
    if not races:
        raise ValueError('NAR race menu has no published racecards')
    return races


def discover_nar(days):
    calendars, pending, errors, urls = {}, [], [], {}
    for day in days:
        month = (day.year, day.month)
        try:
            if month not in calendars:
                calendar = NAR + NAR_CALENDAR + '?' + urlencode(dict(zip(('k_year', 'k_month'), month)))
                calendars[month] = nar_page(calendar)
            pending.extend((day, code, url) for code, url in nar_meetings(calendars[month], day).items())
        except (OSError, ValueError) as error:
            errors.append(f'{day} NAR calendar: {error}')
    with ThreadPoolExecutor(max_workers=4) as pool:
        for day, code, url, future in [(day, code, url, pool.submit(nar_page, url)) for day, code, url in pending]:
            try:
                urls.update(nar_racecard_links(future.result(), day, code))
            except (OSError, ValueError) as error:
                errors.append(f'{day} NAR {VENUES[code][0]}: {error}')
    return urls, errors


def nar_result_url(card_url):
    day, code, race = nar_identity(card_url)
    return NAR + NAR_DAY + 'RaceMarkTable?' + urlencode({
        'k_raceDate': date.fromisoformat(day).strftime('%Y/%m/%d'), 'k_babaCode': code, 'k_raceNo': race,
    })
