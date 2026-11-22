"""Fetch a user-supplied JRA official racecard URL; never invent missing runners.

HTTP retrieval is real. HTML extraction is intentionally fail-closed: if the
official markup changes or horse numbers cannot be identified, no racecard is saved.
"""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
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

def fetch_jra(url, timeout=15):
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.hostname not in ('www.jra.go.jp','jra.go.jp') or not parts.path.startswith('/JRADB/'):
        raise ValueError('only JRA official HTTPS JRADB URLs allowed')
    req=Request(url,headers={'User-Agent':'PRISM-Racecard-Research/0.1 (official-source reader)'})
    with urlopen(req,timeout=timeout) as response:
        final=urlsplit(response.geturl())
        if final.scheme!='https' or final.hostname not in ('www.jra.go.jp','jra.go.jp'):
            raise ValueError('redirected outside official domain')
        body=response.read(3_000_001)
        if len(body)>3_000_000:raise ValueError('source too large')
        encoding=response.headers.get_content_charset() or 'shift_jis'
    html=body.decode(encoding,errors='strict')
    runners=extract_jra_rows(html)
    return {'schema':'prism.official_racecard_fetch/v1','authority':'JRA',
            'official_url':response.geturl(),'captured_at':datetime.now(timezone.utc).isoformat(),
            'source_sha256':hashlib.sha256(body).hexdigest(),'runners':runners,
            'source_verified':False,
            'note':'Retrieved from JRA domain; official HTML layout and race identity require independent validation before PRE_AVAILABLE prediction.'}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--url',required=True);p.add_argument('--out',required=True)
    args=p.parse_args()
    result=fetch_jra(args.url)
    with Path(args.out).open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'runners':len(result['runners']),'captured_at':result['captured_at'],'source_sha256':result['source_sha256']}))

if __name__=='__main__':main()
