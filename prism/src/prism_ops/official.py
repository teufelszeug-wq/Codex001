"""Official-source snapshots and conservative JRA/NAR normalization.

Raw source bytes belong in the configured private evidence directory. A fetched
page is not a parsed racecard. Unsupported layouts, missing identities, and
unpublished results raise rather than manufacturing a race. Parsing requires
the project's ``research`` extra (lxml).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


OFFICIAL_HOSTS = {
    "jra.go.jp": "JRA", "www.jra.go.jp": "JRA",
    "keiba.go.jp": "NAR", "www.keiba.go.jp": "NAR", "sp.keiba.go.jp": "NAR",
}
NAR_VENUES = {
    "03": "帯広", "10": "盛岡", "11": "水沢", "18": "浦和",
    "19": "船橋", "20": "大井", "21": "川崎", "22": "金沢",
    "23": "笠松", "24": "名古屋", "27": "園田", "28": "姫路",
    "30": "門別", "31": "高知", "32": "佐賀",
}
JRA_VENUES = {"札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
              "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10"}
RESULT_HASH_KEYS = (
    "race_id", "published_at", "payouts", "refunds", "complete_payouts",
    "status", "refunded_bet_types", "revision", "correction_of",
    "publication_status", "first_observed_at", "complete_bet_types",
)
BET_TYPES = {
    "単勝": ("WIN", 1), "複勝": ("PLACE", 1),
    "枠連複": ("FRAME_QUINELLA", 2), "枠連単": ("FRAME_EXACTA", 2),
    "馬連複": ("QUINELLA", 2), "馬連単": ("EXACTA", 2),
    "ワイド": ("WIDE", 2), "三連複": ("TRIO", 3), "三連単": ("TRIFECTA", 3),
}


class OfficialSourceError(ValueError):
    """A source cannot safely be used as the requested official race."""


def validate_official_url(url: str, authority: str | None = None) -> str:
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in OFFICIAL_HOSTS
            or parts.username or parts.password or parts.port not in (None, 443)
            or parts.fragment):
        raise OfficialSourceError("only exact official HTTPS hosts without credentials are allowed")
    found = OFFICIAL_HOSTS[parts.hostname]
    if authority is not None and found != authority:
        raise OfficialSourceError("redirect or source changed racing authority")
    return found


class _OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_official_url(newurl, validate_official_url(req.full_url))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _canonical_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _immutable_write(path: Path, body: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(body)
    except FileExistsError:
        if path.read_bytes() != body:
            raise OfficialSourceError("existing evidence differs; refusing overwrite")


def fetch_official_snapshot(url: str, evidence_dir, *, timeout=20,
                            max_bytes=3_000_000, form_cname=None,
                            navigation_snapshot=None) -> dict:
    """Read an official page; POST is limited to published JRA navigation forms.

    The identity-bearing URL remains the source reference for POST navigation;
    response_url and lowercase cname request data are recorded separately.
    """
    authority = validate_official_url(url)
    headers = {"User-Agent": "PRISM/0.1 official-source research reader"}
    request_url, data = url, None
    if form_cname is not None:
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        route = 'd' if parts.path == '/JRADB/accessD.html' else 's' if parts.path == '/JRADB/accessS.html' else None
        index = {'d': 'pw01dli00/F3', 's': 'pw01sli00/AF'}.get(route)
        if authority != 'JRA' or route is None or query != {'CNAME': [form_cname]}:
            raise OfficialSourceError('POST is limited to exact JRA navigation selections')
        if form_cname != index:
            menu = re.fullmatch(r'pw01' + route + r'rl(?:00|01|10)\d{18}/[0-9A-Fa-f]{2}', form_cname)
            if not menu or not isinstance(navigation_snapshot, dict):
                raise OfficialSourceError('JRA form menu requires retained observed doAction evidence')
            source = _document(navigation_snapshot, 'JRA')
            observed = False
            for action in source.xpath('//a/@onclick'):
                match = re.search(r"doAction\(\s*'([^']+)'\s*,\s*'([^']+)'", action)
                if match and match[1] == parts.path and match[2] == form_cname:
                    observed = True
                    break
            if not observed:
                raise OfficialSourceError('JRA form CNAME was not observed in source navigation')
        request_url = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
        data = urlencode({'cname': form_cname}).encode('ascii')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    opener = build_opener(_OfficialRedirect())
    request = Request(request_url, data=data, headers=headers, method='POST' if data is not None else 'GET')
    with opener.open(request, timeout=timeout) as response:
        final_url = response.geturl()
        validate_official_url(final_url, authority)
        if form_cname is not None:
            selected = urlsplit(final_url)
            if selected.path != urlsplit(url).path or parse_qs(selected.query) not in ({}, {'CNAME': [form_cname]}):
                raise OfficialSourceError('JRA form response changed navigation selection')
        if response.status != 200:
            raise OfficialSourceError("official source did not return HTTP 200")
        media_type = response.headers.get_content_type()
        if media_type not in ("text/html", "application/xhtml+xml"):
            raise OfficialSourceError("expected an official HTML page")
        body = response.read(max_bytes + 1)
        if len(body) > max_bytes:
            raise OfficialSourceError("official source exceeds size limit")
        encoding = response.headers.get_content_charset()
    if not body:
        raise OfficialSourceError("official source is empty")
    captured_at = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(body).hexdigest()
    directory = Path(evidence_dir)
    directory.mkdir(parents=True, exist_ok=True)
    raw_path = directory / f"{digest}.html"
    _immutable_write(raw_path, body)
    snapshot = {
        "schema": "prism.official_source_snapshot/v1", "authority": authority,
        "official_url": url if form_cname is not None else final_url, "requested_url": url, "captured_at": captured_at,
        "source_sha256": digest, "body_path": str(raw_path.resolve()),
        "encoding": encoding, "mode": "LIVE_FETCH", "identity_verified": False,
    }
    if form_cname is not None:
        snapshot.update(http_method='POST', posted_cname=form_cname, response_url=final_url)
        if navigation_snapshot is not None:
            snapshot['navigation_source_sha256'] = navigation_snapshot['source_sha256']
    metadata_path = directory / f"{digest}-{_canonical_hash(snapshot)[:16]}.json"
    _immutable_write(metadata_path, (json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n").encode())
    return snapshot


def _document(snapshot: dict, authority: str):
    from lxml import html
    if snapshot.get("authority") != authority:
        raise OfficialSourceError("snapshot authority mismatch")
    validate_official_url(snapshot["official_url"], authority)
    captured = datetime.fromisoformat(snapshot["captured_at"].replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise OfficialSourceError("captured_at must include a timezone")
    body = Path(snapshot["body_path"]).read_bytes()
    if hashlib.sha256(body).hexdigest() != snapshot["source_sha256"]:
        raise OfficialSourceError("source bytes changed since capture")
    encoding = snapshot.get("encoding")
    if encoding:
        try:
            text = body.decode(encoding, errors="strict")
        except (UnicodeError, LookupError) as exc:
            raise OfficialSourceError("source encoding cannot be decoded") from exc
        root = html.fromstring(text)
    else:
        root = html.fromstring(body)
    if "情報がありません" in root.text_content() or root.xpath('//*[contains(@class,"cover_error")]'):
        raise OfficialSourceError("BLOCKED_INPUT: requested official race information is unavailable")
    return root


def _text(node) -> str:
    return " ".join(unicodedata.normalize("NFKC", node.text_content()).split())


def _class(name: str) -> str:
    return f'contains(concat(" ", normalize-space(@class), " "), " {name} ")'


def _nar_identity(root, snapshot, expected_date, expected_venue, expected_race_no, endpoint):
    day = date.fromisoformat(expected_date)
    code = str(expected_venue).zfill(2)
    if code not in NAR_VENUES or not 1 <= int(expected_race_no) <= 12:
        raise OfficialSourceError("unknown NAR venue or race number")
    parts = urlsplit(snapshot["official_url"])
    query = parse_qs(parts.query)
    required = {"k_raceDate": day.strftime("%Y/%m/%d"), "k_babaCode": str(int(code)),
                "k_raceNo": str(int(expected_race_no))}
    if not parts.path.endswith("/" + endpoint) or any(query.get(k) != [v] for k, v in required.items()):
        raise OfficialSourceError("official URL race identity does not match requested race")
    text = _text(root)
    pattern = rf"{day.year}年\s*{day.month}月\s*{day.day}日[^\n]*?第\s*{int(expected_race_no)}競走"
    header = re.search(pattern, text)
    if not header or NAR_VENUES[code] not in re.sub(r"\s", "", header.group()):
        raise OfficialSourceError("official page date, venue, or race number mismatch")
    names = root.xpath('//section[' + _class("raceTitle") + ']//h3')
    if len(names) != 1 or not _text(names[0]):
        raise OfficialSourceError("official race title markup changed")
    return {"race_id": f"NAR-{day:%Y%m%d}-{code}-{int(expected_race_no):02d}",
            "race_date": day.isoformat(), "race_no": int(expected_race_no),
            "venue_code": code, "venue_name": NAR_VENUES[code], "race_name": _text(names[0])}


def _horse_id(anchor, base_url):
    href = urljoin(base_url, anchor.get("href", ""))
    validate_official_url(href)
    query = parse_qs(urlsplit(href).query)
    values = query.get("k_lineageLoginCode", [])
    if len(values) != 1 or not re.fullmatch(r"\d{8,14}", values[0]):
        raise OfficialSourceError("official horse ID is missing or ambiguous")
    return values[0]


def _card(snapshot, identity, runners, start_at, stage):
    if len(runners) < 2 or len({r["horse_id"] for r in runners}) != len(runners):
        raise OfficialSourceError("missing or duplicate official runners")
    numbered = [r["horse_no"] for r in runners if r["horse_no"] is not None]
    if len(numbered) != len(set(numbered)) or any(not 1 <= n <= 18 for n in numbered):
        raise OfficialSourceError("duplicate official horse numbers")
    active = [r for r in runners if r["status"] == "DECLARED"]
    return {"schema": "prism.official_racecard/v2", "authority": snapshot["authority"],
            **identity, "start_at": start_at, "off_at": start_at,
            "declaration_stage": stage, "runners": runners, "active_runners": active,
            "captured_at": snapshot["captured_at"], "official_url": snapshot["official_url"],
            "source_sha256": snapshot["source_sha256"], "source_evidence": dict(snapshot),
            "source_verified": snapshot.get("mode") == "LIVE_FETCH",
            "mode": snapshot.get("mode", "SYNTHETIC")}


def parse_nar_racecard(snapshot: dict, *, expected_date: str, expected_venue,
                       expected_race_no: int) -> dict:
    root = _document(snapshot, "NAR")
    identity = _nar_identity(root, snapshot, expected_date, expected_venue, expected_race_no, "DebaTable")
    # A result page and past-race times must not be mistaken for today's start.
    headers = root.xpath('//article[' + _class("raceCard") + ']')
    header_text = _text(headers[0]) if headers else ""
    found = re.search(rf'第\s*{int(expected_race_no)}競走\s*(\d{{1,2}}):(\d{{2}})発走', header_text)
    if not found or int(found[1]) > 23 or int(found[2]) > 59:
        raise OfficialSourceError("official start time is unavailable")
    start_at = f"{expected_date}T{int(found[1]):02d}:{found[2]}:00+09:00"
    runners = []
    frame = None
    for row in root.xpath('//tr[td[' + _class("horseNum") + ']]'):
        number_nodes = row.xpath('./td[' + _class("horseNum") + ']')
        anchors = row.xpath('.//a[' + _class("horseName") + ']')
        frame_nodes = row.xpath('./td[' + _class("courseNum") + ']')
        if not anchors and _text(number_nodes[0]) in ("馬番", "馬番号"):
            continue  # The official page also contains a labelled legend table.
        if len(anchors) != 1 or not re.fullmatch(r"\d{1,2}", _text(number_nodes[0])):
            raise OfficialSourceError("official runner markup changed")
        if frame_nodes:
            if not re.fullmatch(r"[1-8]", _text(frame_nodes[0])):
                raise OfficialSourceError("official frame number is invalid")
            frame = int(_text(frame_nodes[0]))
        if frame is None:
            raise OfficialSourceError("official frame number is unavailable")
        name = _text(anchors[0])
        if not name or name in ("馬名", "取消", "除外"):
            raise OfficialSourceError("official horse name is unavailable")
        # Current changes occur in odds/weight cells, not historical result cells.
        block = [row]
        for sibling in list(row.itersiblings())[:4]:
            if sibling.xpath('./td[' + _class("horseNum") + ']'):
                break
            block.append(sibling)
        changes = " ".join(_text(c) for r in block for c in r.xpath('./td[' + _class("odds_weight") + ']'))
        status = "SCRATCHED" if any(x in changes for x in ("取消", "除外")) else "DECLARED"
        runners.append({"horse_id": _horse_id(anchors[0], snapshot["official_url"]),
                        "horse_name": name, "horse_no": int(_text(number_nodes[0])),
                        "frame_no": frame, "status": status})
    if len(root.xpath('//a[' + _class("horseName") + ']')) != len(runners):
        raise OfficialSourceError("official runner was omitted by changed markup")
    return _card(snapshot, identity, runners, start_at, "DRAW_CONFIRMED")


def parse_nar_result(snapshot: dict, *, expected_date: str, expected_venue,
                     expected_race_no: int) -> dict:
    root = _document(snapshot, "NAR")
    identity = _nar_identity(root, snapshot, expected_date, expected_venue, expected_race_no, "RaceMarkTable")
    payouts, unsupported_payouts = [], []
    complete_types = set()
    for table in root.xpath('//table[.//td[' + _class("refundMoney") + ']]'):
        kind = None
        remaining = 0
        for row in table.xpath('./tbody/tr|./tr'):
            cells = row.xpath('./td')
            titles = row.xpath('./td[' + _class("title") + ']')
            if titles:
                if remaining:
                    raise OfficialSourceError("official payout group is incomplete")
                label = _text(titles[0])
                if label not in BET_TYPES:
                    raise OfficialSourceError("unsupported official payout type")
                kind = BET_TYPES[label]
                span = titles[0].get("rowspan", "1")
                if not span.isdigit() or not 1 <= int(span) <= 50:
                    raise OfficialSourceError("invalid official payout group span")
                remaining = int(span)
            money = row.xpath('./td[' + _class("refundMoney") + ']')
            if not money:
                raise OfficialSourceError("incomplete official payout row")
            if kind is None or len(money) != 1:
                raise OfficialSourceError("ambiguous official payout type")
            index = cells.index(money[0])
            if index == 0:
                raise OfficialSourceError("official winning combination is missing")
            combination = _text(cells[index - 1])
            amount = _text(money[0])
            if not re.fullmatch(r"\d{1,2}(?:-\d{1,2})*", combination) or not re.fullmatch(r"[\d,]+円", amount):
                raise OfficialSourceError("unsupported refund, cancellation, or payout markup")
            numbers = [int(v) for v in combination.split("-")]
            if len(numbers) != kind[1] or any(v < 1 or v > 18 for v in numbers):
                raise OfficialSourceError("invalid official payout combination")
            if kind[0] not in ("FRAME_QUINELLA", "FRAME_EXACTA") and len(set(numbers)) != len(numbers):
                raise OfficialSourceError("repeated horse in official payout")
            if kind[0] in ("WIN", "PLACE", "QUINELLA", "WIDE", "TRIO", "FRAME_QUINELLA"):
                numbers.sort()
            key = "frame_nos" if kind[0].startswith("FRAME_") else "horse_nos"
            parsed = {"type": kind[0], key: numbers, "payout_per_100_yen": int(amount[:-1].replace(",", ""))}
            if parsed["payout_per_100_yen"] <= 0:
                raise OfficialSourceError("official payout must be positive")
            if kind[0] == "FRAME_EXACTA":
                unsupported_payouts.append(parsed)
            else:
                payouts.append(parsed)
            remaining -= 1
            if remaining < 0:
                raise OfficialSourceError("official payout group has unexpected rows")
            if remaining == 0 and kind[0] != "FRAME_EXACTA":
                complete_types.add(kind[0])
        if remaining:
            raise OfficialSourceError("official payout group is incomplete")
    if not payouts:
        raise OfficialSourceError("official payouts are not published or markup changed")
    keys = [(p["type"], tuple(p.get("horse_nos", p.get("frame_nos", [])))) for p in payouts]
    if len(set(keys)) != len(keys):
        raise OfficialSourceError("duplicate official payout combination")
    # NAR pages do not expose an exact publication timestamp. Capture is an
    # observation bound, never an invented official publication timestamp.
    uncertain_refunds = any(marker in _text(root) for marker in ("取消", "除外", "返還", "競走取りやめ", "競走取止"))
    result = {"race_id": identity["race_id"], "official_source": snapshot["official_url"],
              "published_at": None, "publication_status": "UNKNOWN_TIMESTAMP",
              "first_observed_at": snapshot["captured_at"], "payouts": payouts,
              "refunds": [], "complete_payouts": not uncertain_refunds, "status": "FINAL",
              "complete_bet_types": sorted(complete_types) if not uncertain_refunds else [],
              "settlement_ready": not uncertain_refunds,
              "mode": "OFFICIAL" if snapshot.get("mode") == "LIVE_FETCH" else "SYNTHETIC",
              "race_identity": identity, "unsupported_payouts": unsupported_payouts}
    # Cancelled/excluded runners require an explicit refund audit. Such pages
    # retain individually parsed payouts but cannot mark an unlisted bet lost.
    normalized = {key: result[key] for key in RESULT_HASH_KEYS if key in result}
    result["source_snapshot"] = {"official_url": snapshot["official_url"],
        "captured_at": snapshot["captured_at"], "source_sha256": snapshot["source_sha256"],
        "normalized_sha256": _canonical_hash(normalized)}
    return result


def parse_jra_racecard(snapshot: dict, *, expected_date: str, expected_venue: str,
                       expected_race_no: int, expected_race_name: str | None = None) -> dict:
    """Parse explicit official entries including Thursday declarations before draw.

    This accepts only pages exposing a date, venue, race number, start time, and
    real horse profile IDs. An unsupported JRADB layout stays BLOCKED_INPUT.
    """
    root = _document(snapshot, "JRA")
    day = date.fromisoformat(expected_date)
    if expected_venue not in JRA_VENUES or not 1 <= int(expected_race_no) <= 12:
        raise OfficialSourceError("unknown JRA venue or race number")
    cname = parse_qs(urlsplit(snapshot["official_url"]).query).get("CNAME", [])
    url_identity = re.fullmatch(r"pw01dde01(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})(\d{8})/[A-Za-z0-9]+", cname[0]) if len(cname) == 1 else None
    if (not url_identity or url_identity[1] != JRA_VENUES[expected_venue]
            or url_identity[2] != str(day.year) or int(url_identity[5]) != int(expected_race_no)
            or url_identity[6] != day.strftime("%Y%m%d")):
        raise OfficialSourceError("official JRA URL race identity mismatch")
    headings = root.xpath('//h1')
    text = " ".join(_text(h) for h in headings)
    if (not re.search(rf"{day.year}年\s*{day.month}月\s*{day.day}日", text)
            or expected_venue not in text
            or not re.search(rf"(?<!\d){int(expected_race_no)}\s*(?:R|レース)", text)):
        raise OfficialSourceError("official JRA page race identity mismatch")
    race_headers = root.xpath('//div[' + _class("race_header") + ']')
    if len(race_headers) != 1:
        raise OfficialSourceError("official JRA race header markup changed")
    header_text = _text(race_headers[0])
    if not expected_race_name or expected_race_name not in header_text:
        raise OfficialSourceError("explicit JRA race title required for identity verification")
    found = re.search(r"発走(?:時刻)?[^\d]{0,5}(\d{1,2})[:時](\d{2})(?:分)?|(?<!\d)(\d{1,2}):(\d{2})\s*発走", header_text)
    if found:
        hour, minute = (found[1], found[2]) if found[1] else (found[3], found[4])
    if not found or int(hour) > 23 or int(minute) > 59:
        raise OfficialSourceError("official JRA start time is unavailable")
    runners = []
    frame = None
    # Non-selected/non-drawn horses have separate ``horse`` cells without the
    # declared runner's num column. They must not enter the race field.
    for row in root.xpath('//tr[td[' + _class("horse") + '] and td[' + _class("num") + ' or ' + _class("horse_num") + ']]'):
        links = row.xpath('.//a[contains(@href,"pw01dud") or contains(@href,"horse_id=")]')
        if not links:
            raise OfficialSourceError("declared JRA runner is missing an official horse ID")
        if len(links) != 1:
            raise OfficialSourceError("ambiguous JRA horse identity")
        link = links[0]
        href = urljoin(snapshot["official_url"], link.get("href", ""))
        validate_official_url(href, "JRA")
        match = re.search(r"(?:pw01dud00|horse_id=)(\d{10})", href)
        if not match or not _text(link):
            raise OfficialSourceError("official JRA horse ID missing")
        number_cells = row.xpath('./td[' + _class("num") + ']|./td[' + _class("horse_num") + ']')
        frame_cells = row.xpath('./td[' + _class("waku") + ']')
        number = int(_text(number_cells[0])) if number_cells and re.fullmatch(r"\d{1,2}", _text(number_cells[0])) else None
        if frame_cells:
            images = frame_cells[0].xpath('./img/@src')
            match_frame = re.search(r"/waku/([1-8])\.png$", images[0]) if images else None
            if match_frame:
                frame = int(match_frame[1])
            elif re.fullmatch(r"[1-8]", _text(frame_cells[0])):
                frame = int(_text(frame_cells[0]))
            elif _text(frame_cells[0]) or images:
                raise OfficialSourceError("official JRA frame markup changed")
        runners.append({"horse_id": match[1], "horse_name": _text(link), "horse_no": number,
                        "frame_no": frame if number is not None else None,
                        "status": "SCRATCHED" if "取消" in _text(row.xpath('./td[' + _class("horse") + ']')[0]) else "DECLARED"})
    if any(r["horse_no"] is not None for r in runners) and not all(r["horse_no"] and r["frame_no"] for r in runners):
        raise OfficialSourceError("partial JRA draw must not be treated as complete")
    stage = "DRAW_CONFIRMED" if runners and all(r["horse_no"] and r["frame_no"] for r in runners) else "ENTRIES_CONFIRMED"
    identity = {"race_id": f"JRA-{day:%Y%m%d}-{JRA_VENUES[expected_venue]}-{int(expected_race_no):02d}",
                "race_name": expected_race_name, "race_date": expected_date,
                "venue_name": expected_venue, "venue_code": JRA_VENUES[expected_venue],
                "race_no": int(expected_race_no)}
    return _card(snapshot, identity, runners,
                 f"{expected_date}T{int(hour):02d}:{minute}:00+09:00", stage)


def jra_url_identity(url: str, *, result=False) -> dict:
    """Decode a published official race link; never generate CNAME checksums."""
    validate_official_url(url, "JRA")
    parts = urlsplit(url)
    endpoint = "/JRADB/accessS.html" if result else "/JRADB/accessD.html"
    query = parse_qs(parts.query)
    code = query.get("CNAME", [])
    prefix = r"pw01sde(?:01|10)" if result else r"pw01dde01"
    found = re.fullmatch(prefix + r"(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})(\d{8})/[0-9A-Fa-f]{2}",
                         code[0]) if len(code) == 1 else None
    if parts.path != endpoint or not found:
        raise OfficialSourceError("explicit official JRA race URL required")
    venue, year, meeting, meeting_day, race_no, day = found.groups()
    reverse = {code: name for name, code in JRA_VENUES.items()}
    try:
        race_date = datetime.strptime(day, "%Y%m%d").date()
    except ValueError as exc:
        raise OfficialSourceError("invalid JRA date in official URL") from exc
    if venue not in reverse or year != str(race_date.year) or not 1 <= int(race_no) <= 12 or not int(meeting) or not int(meeting_day):
        raise OfficialSourceError("invalid JRA race identity in official URL")
    return {"race_id": f"JRA-{day}-{venue}-{int(race_no):02d}",
            "race_date": race_date.isoformat(), "venue_code": venue,
            "venue_name": reverse[venue], "race_no": int(race_no),
            "meeting": int(meeting), "meeting_day": int(meeting_day)}


def parse_jra_result(snapshot: dict, *, expected_date: str, expected_venue: str,
                     expected_race_no: int, expected_race_name: str | None = None) -> dict:
    """Adapt PR #12's official finish/payout parser to immutable snapshot evidence.

    Source: ``fetch_official_result.py`` at 18ba748. Publication time is unknown;
    collection time remains first_observed_at. Refund-ambiguous races stay held.
    """
    root = _document(snapshot, "JRA")
    identity = jra_url_identity(snapshot["official_url"], result=True)
    if (identity["race_date"] != expected_date or identity["venue_name"] != expected_venue or
            identity["race_no"] != int(expected_race_no)):
        raise OfficialSourceError("official JRA result URL race identity mismatch")
    headers = root.xpath('//div[' + _class("race_header") + ']')
    if len(headers) != 1:
        raise OfficialSourceError("official JRA result header required")
    header = headers[0]
    dates = header.xpath('.//*[' + _class("date") + ']')
    heading = _text(dates[0]) if len(dates) == 1 else ""
    day = date.fromisoformat(expected_date)
    race_alts = header.xpath('.//img[contains(@alt,"レース")]/@alt')
    if (not re.search(rf"{day.year}年\s*{day.month}月\s*{day.day}日", heading) or
            not re.search(rf'{identity["meeting"]}回\s*{re.escape(expected_venue)}\s*{identity["meeting_day"]}日', heading) or
            f"{identity['race_no']}レース" not in race_alts):
        raise OfficialSourceError("official JRA result header does not match requested race")
    titles = header.xpath('.//*[' + _class("race_name") + ']')
    name = _text(titles[0]) if len(titles) == 1 else None
    if expected_race_name is not None and name != expected_race_name:
        raise OfficialSourceError("official JRA result race title mismatch")
    identity = {**identity, "race_name": name}
    tables = root.xpath('//table[thead//th[' + _class("place") + '] and thead//th[' + _class("horse") + ']]')
    units = root.xpath('//*[' + _class("refund_unit") + ']')
    if len(tables) != 1 or len(units) != 1:
        raise OfficialSourceError("final JRA finish and payout tables required")
    finishers = []
    for row in tables[0].xpath('./tbody/tr[td]'):
        cells = {key: row.xpath('./td[' + _class(key) + ']') for key in ("place", "num", "horse")}
        if any(len(value) != 1 for value in cells.values()):
            raise OfficialSourceError("incomplete official JRA finisher row")
        position, number, horse_name = (_text(cells[key][0]) for key in ("place", "num", "horse"))
        if not re.fullmatch(r"\d{1,2}", number) or not 1 <= int(number) <= 18 or not horse_name:
            raise OfficialSourceError("invalid official JRA finisher identity")
        placed = re.fullmatch(r"(\d{1,2})(?:着|同着)?", position)
        if placed and int(placed[1]) > 0:
            place, status = int(placed[1]), "FINISHED"
        else:
            statuses = {"取消": "SCRATCHED", "出走取消": "SCRATCHED", "除外": "EXCLUDED",
                        "競走除外": "EXCLUDED", "中止": "DNF", "競走中止": "DNF", "失格": "DISQUALIFIED"}
            if position not in statuses:
                raise OfficialSourceError("unsupported official JRA finish status")
            place, status = None, statuses[position]
        finishers.append({"horse_no": int(number), "horse_name": horse_name,
                          "finish": place, "status": status, "official_status": position})
    if not finishers or len({r["horse_no"] for r in finishers}) != len(finishers):
        raise OfficialSourceError("complete unique official JRA finisher list required")
    types = {**BET_TYPES, "枠連": ("FRAME_QUINELLA", 2), "馬連": ("QUINELLA", 2),
             "馬単": ("EXACTA", 2), "3連複": ("TRIO", 3), "3連単": ("TRIFECTA", 3)}
    payouts, unsupported, complete, groups = [], [], set(), set()
    for item in units[0].xpath('.//li[dl/dt]'):
        labels = item.xpath('./dl/dt')
        if len(labels) != 1:
            raise OfficialSourceError("ambiguous JRA payout group")
        label = _text(labels[0])
        if label == "WIN5":
            continue  # A separate multi-race product, outside this race's eight tickets.
        if label not in types:
            raise OfficialSourceError("unsupported official JRA payout type")
        kind, leg_count = types[label]
        if kind in groups:
            raise OfficialSourceError("duplicate JRA payout group")
        groups.add(kind)
        lines = item.xpath('.//*[' + _class("line") + ']')
        if not lines:
            raise OfficialSourceError("official JRA payout group is incomplete")
        count = 0
        for line in lines:
            numbers = line.xpath('.//*[' + _class("num") + ']')
            money = line.xpath('.//*[' + _class("yen") + ']')
            if len(numbers) != 1 or len(money) != 1:
                raise OfficialSourceError("ambiguous JRA payout combination or amount")
            legs = " ".join(unicodedata.normalize("NFKC", t).strip() for t in numbers[0].itertext()).strip()
            amount = _text(money[0])
            if legs in ("", "-", "－") and amount in ("", "-", "－"):
                continue  # Unavailable type is never declared complete.
            if not re.fullmatch(r"\d{1,2}(?:\s*[-–−]?\s*\d{1,2})*", legs) or not re.fullmatch(r"[\d,]+円", amount):
                raise OfficialSourceError("unsupported JRA refund or payout markup")
            values = [int(v) for v in re.findall(r"\d+", legs)]
            maximum = 8 if kind.startswith("FRAME_") else 18
            if (len(values) != leg_count or any(not 1 <= v <= maximum for v in values) or
                    not kind.startswith("FRAME_") and len(set(values)) != len(values)):
                raise OfficialSourceError("invalid official JRA payout combination")
            if not kind.startswith("FRAME_") and not set(values) <= {r["horse_no"] for r in finishers if r["status"] not in {"SCRATCHED", "EXCLUDED"}}:
                raise OfficialSourceError("JRA payout refers to a missing or refunded horse")
            if kind in {"WIN", "PLACE", "QUINELLA", "WIDE", "TRIO", "FRAME_QUINELLA"}:
                values.sort()
            yen = int(amount[:-1].replace(",", ""))
            if yen <= 0:
                raise OfficialSourceError("official JRA payout must be positive")
            key = "frame_nos" if kind.startswith("FRAME_") else "horse_nos"
            parsed = {"type": kind, key: values, "payout_per_100_yen": yen}
            (unsupported if kind == "FRAME_EXACTA" else payouts).append(parsed)
            count += 1
        if count and kind != "FRAME_EXACTA":
            complete.add(kind)
    keys = [(r["type"], tuple(r.get("horse_nos", r.get("frame_nos", [])))) for r in payouts]
    if not payouts or len(keys) != len(set(keys)):
        raise OfficialSourceError("missing or duplicate official JRA payouts")
    winners = {r["horse_no"] for r in finishers if r["finish"] == 1}
    win_tickets = [r["horse_nos"][0] for r in payouts if r["type"] == "WIN"]
    if not winners or len(win_tickets) != len(winners) or winners != set(win_tickets):
        raise OfficialSourceError("official JRA win payouts do not match all first-place finishers")
    uncertain = any(r["status"] in {"SCRATCHED", "EXCLUDED"} for r in finishers) or any(
        marker in _text(units[0]) for marker in ("返還", "取りやめ", "取止", "特払"))
    result = {"race_id": identity["race_id"], "official_source": snapshot["official_url"],
              "published_at": None, "publication_status": "UNKNOWN_TIMESTAMP",
              "first_observed_at": snapshot["captured_at"], "payouts": payouts,
              "refunds": [], "complete_payouts": not uncertain, "status": "FINAL",
              "complete_bet_types": sorted(complete) if not uncertain else [],
              "settlement_ready": not uncertain,
              "mode": "OFFICIAL" if snapshot.get("mode") == "LIVE_FETCH" else "SYNTHETIC",
              "race_identity": identity, "finishers": finishers, "unsupported_payouts": unsupported}
    normalized = {key: result[key] for key in RESULT_HASH_KEYS if key in result}
    result["source_snapshot"] = {"official_url": snapshot["official_url"],
        "captured_at": snapshot["captured_at"], "source_sha256": snapshot["source_sha256"],
        "normalized_sha256": _canonical_hash(normalized)}
    return result
