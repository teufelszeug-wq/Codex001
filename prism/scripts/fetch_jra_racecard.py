"""Fetch a user-supplied JRA official racecard URL; never invent missing runners.

HTTP retrieval is real. HTML extraction is intentionally fail-closed: if the
official markup changes or horse numbers cannot be identified, no racecard is saved.
"""
from html.parser import HTMLParser
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import parse_qs, urlsplit
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import hashlib
import argparse

class TableRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows=[];self.row=None;self.cell=None;self.in_table=0
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.in_table+=1
        elif tag=='tr' and self.in_table and self.row is None:self.row=[]
        elif tag in ('td','th') and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(re.sub(r'\s+',' ',''.join(self.cell)).strip());self.cell=None
        elif tag=='tr' and self.row is not None:
            if self.row:self.rows.append(self.row)
            self.row=None
        elif tag=='table':self.in_table=max(0,self.in_table-1)

def extract_jra_rows(html):
    parser=TableRows();parser.feed(html)
    horses=[]
    for cells in parser.rows:
        # Racecard's initial columns are frame, horse number, horse name/trainer.
        # Require explicit horse number; never infer from row order.
        if len(cells)<4:continue
        number=cells[1].strip()
        if not re.fullmatch(r'\d{1,2}',number):continue
        horse_name=cells[2].split(' ')[0].strip()
        if not horse_name or len(horse_name)>40 or horse_name in ('馬名','取消','除外'):continue
        horses.append({'horse_no':int(number),'horse_name':horse_name,'status':'DECLARED'})
    if len(horses)<2 or len({h['horse_no'] for h in horses})!=len(horses):
        raise ValueError('cannot reliably extract official horse numbers and names; source markup needs review')
    return sorted(horses,key=lambda h:h['horse_no'])

def official_jra_url(url):
    parts=urlsplit(url)
    if (parts.scheme!='https' or parts.hostname not in ('www.jra.go.jp','jra.go.jp')
            or parts.username or parts.password or parts.port not in (None, 443)
            or not parts.path.startswith('/JRADB/')):
        raise ValueError('only JRA official HTTPS JRADB URLs allowed')
    return parts


class OfficialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official_jra_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def racecard_identity(url):
    parts = official_jra_url(url)
    cnames = parse_qs(parts.query).get('CNAME', [])
    match = re.fullmatch(r'pw01dde01(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})(\d{8})/[A-F0-9]{2}',
                         cnames[0]) if len(cnames) == 1 else None
    if parts.path != '/JRADB/accessD.html' or not match:
        raise ValueError('JRA official numbered racecard URL required')
    venue_code, year, meeting, day, race_no, race_date = match.groups()
    venues = dict(zip((f'{i:02d}' for i in range(1, 11)), (
        ('札幌', 'SAPPORO'), ('函館', 'HAKODATE'), ('福島', 'FUKUSHIMA'), ('新潟', 'NIIGATA'),
        ('東京', 'TOKYO'), ('中山', 'NAKAYAMA'), ('中京', 'CHUKYO'), ('京都', 'KYOTO'),
        ('阪神', 'HANSHIN'), ('小倉', 'KOKURA'),
    )))
    if venue_code not in venues or year != race_date[:4] or not 1 <= int(race_no) <= 12:
        raise ValueError('invalid JRA race identity')
    venue, venue_id = venues[venue_code]
    return race_date, venue, venue_id, int(meeting), int(day), int(race_no)


def read_jra(url, timeout=15):
    official_jra_url(url)
    req=Request(url,headers={'User-Agent':'PRISM-Racecard-Research/0.1 (official-source reader)'})
    with build_opener(OfficialRedirect).open(req,timeout=timeout) as response:
        final_url = response.geturl()
        official_jra_url(final_url)
        body=response.read(3_000_001)
        if len(body)>3_000_000:raise ValueError('source too large')
        encoding=response.headers.get_content_charset() or 'cp932'
    return final_url, body, body.decode(encoding,errors='strict')


def fetch_jra(url, timeout=15):
    final_url, body, html = read_jra(url, timeout)
    runners=extract_jra_rows(html)
    return {'schema':'prism.official_racecard_fetch/v1','authority':'JRA',
            'official_url':final_url,'captured_at':datetime.now(timezone.utc).isoformat(),
            'source_sha256':hashlib.sha256(body).hexdigest(),'runners':runners,
            'source_verified':False,
            'note':'Retrieved from JRA domain; official HTML layout and race identity require independent validation before PRE_AVAILABLE prediction.'}


def fetch_for_forecast(url, timeout=15, allow_unframed=False):
    from jra_forecast_card import parse_forecast_card

    identity = racecard_identity(url)
    final_url, body, html = read_jra(url, timeout)
    if racecard_identity(final_url) != identity:
        raise ValueError('JRA response changed race identity')
    card = parse_forecast_card(html, identity, datetime.now(timezone.utc), allow_unframed)
    return {**card, 'official_url': final_url, 'source_sha256': hashlib.sha256(body).hexdigest()}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url',required=True);p.add_argument('--out',required=True)
    p.add_argument('--for-forecast', action='store_true', help='Verify race identity and extract forecast inputs')
    p.add_argument('--allow-unframed', action='store_true', help='Also save confirmed entries before horse numbers are published')
    args=p.parse_args()
    if args.allow_unframed and not args.for_forecast:
        p.error('--allow-unframed requires --for-forecast')
    result=fetch_for_forecast(args.url, allow_unframed=args.allow_unframed) if args.for_forecast else fetch_jra(args.url)
    with Path(args.out).open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'runners':len(result['runners']),'captured_at':result['captured_at'],'source_sha256':result['source_sha256']}))

if __name__=='__main__':main()
