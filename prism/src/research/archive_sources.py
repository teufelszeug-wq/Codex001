"""Archive parser. Result-bearing objects must stay in evaluator/controller only."""
import csv
import io
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

def clean(s):
    return ''.join(unicodedata.normalize('NFKC', s).split())

def integer(s):
    m=re.search(r'\d+', clean(s).replace(',',''))
    return int(m.group()) if m else None

def num(s):
    try: return float(clean(s))
    except ValueError: return None

def nar_archive(path):
    with ZipFile(path) as z:
        tables={}
        for k in ('racelist','horselist','payback'):
            name=next(n for n in z.namelist() if n.endswith('_'+k+'.csv'))
            tables[k]=list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))
    key=lambda r:(r['競走年月日'],r['競馬場'],r['レース番号'])
    horses=defaultdict(list); payouts=defaultdict(list)
    for r in tables['horselist']: horses[key(r)].append(r)
    for r in tables['payback']: payouts[key(r)].append(r)
    out=[]
    for r in tables['racelist']:
        date,venue,no=key(r); tt=r['発走時刻'].zfill(4)
        surface='BANEI' if venue=='帯広ば' else ('TURF' if '芝' in r['芝ダート区分'] else 'DIRT')
        entrants=[]; results=[]
        for h in sorted(horses[key(r)],key=lambda h:int(h['馬番'])):
            number=int(h['馬番']); counts={}
            for field in ('全成績','当競馬場成績','うち当距離成績'):
                parts=re.findall(r'\d+',clean(h[field]))
                counts[field]=list(map(int,parts)) if len(parts)==4 else None
            ident='NAR|'+ '|'.join(clean(h[k]) for k in ('馬名','生年月日','父馬名','母馬名'))
            entrants.append(dict(number=number,frame=integer(h['枠番']),name=clean(h['馬名']),identity=ident,
                                 identity_quality='NAME_BIRTH_PARENTS',career=counts,age=integer(h['齢']),
                                 weight=num(h['負担重量'])))
            rank=clean(h['着順'])
            status=rank or {'出走取消':'取消','競走除外':'除外','競走中止':'中止','失格':'失格'}.get(clean(h['着差']),'UNKNOWN')
            results.append(dict(number=number,rank=int(rank) if rank.isdigit() else None,status=status))
        pay={}
        for p in payouts[key(r)]:
            winner=integer(p['単勝組番']); yen=integer(p['単勝払戻金（円）'])
            if winner and yen: pay[str(winner)]=yen
        out.append(dict(race_id=f'NAR|{date}|{venue}|{no}',date=date,start=tt,venue=venue,number=int(no),
            authority='NAR',surface=surface,distance=int(r['距離']),direction={'右':'RIGHT','左':'LEFT','直':'STRAIGHT'}.get(r['回り'],'STRAIGHT' if surface=='BANEI' else 'MIXED'),
            title=r['レース名'],entrants=entrants,results=results,win_payouts=pay,
            source=str(path),source_kind='NAR_OFFICIAL_MONTHLY_CSV'))
    return out

def jra_page(path):
    from lxml import html
    root=html.fromstring(Path(path).read_bytes())
    def txt(e): return clean(e.text_content())
    def first(xpath):
        rows=root.xpath(xpath)
        return txt(rows[0]) if rows else ''
    date_text=first('//div[contains(@class,"cell date")]')
    m=re.search(r'(\d{4})年(\d+)月(\d+)日.*?\d+回(.+?)\d+日',date_text)
    if not m: raise ValueError('missing JRA date/venue: '+str(path))
    year,month,day,venue=m.groups(); date=f'{int(year):04d}{int(month):02d}{int(day):02d}'
    time=first('//div[contains(@class,"cell time")]');tm=re.search(r'(\d+)時(\d+)分',time)
    if not tm: raise ValueError('missing JRA start time')
    start=f'{int(tm[1]):02d}{int(tm[2]):02d}'
    no=root.xpath('//div[@class="race_number"]//img/@alt'); number=integer(no[0]) if no else None
    if not number: raise ValueError('missing JRA number')
    title=first('//span[@class="race_name"]')
    course=first('//div[contains(@class,"cell course")]')
    dist=re.search(r'([\d,]+)メートル',course)
    if not dist: raise ValueError('missing JRA distance')
    surface='JUMP' if '障害' in title else ('DIRT' if 'ダート' in course else 'TURF')
    direction='LEFT' if '左' in course else ('RIGHT' if '右' in course else 'MIXED')
    entrants=[];results=[]
    for tr in root.xpath('//table[contains(@class,"striped")]//tr[td]'):
        cells={td.get('class'):txt(td) for td in tr.xpath('./td')}
        if not cells.get('num'): continue
        n=integer(cells['num']); sexage=cells.get('age','');age=integer(sexage)
        # No raw row order: result tables are finish-order sorted.
        name=cells.get('horse','');sex=re.sub(r'\d','',sexage)
        ident='JRA|'+name+'|'+sex+'|'+str(int(year)-age if age is not None else '?')
        entrants.append(dict(number=n,frame=integer(cells.get('waku','')),name=name,identity=ident,
            identity_quality='PROVISIONAL_NAME_SEX_BIRTHYEAR',career={},age=age,weight=num(cells.get('weight',''))))
        rank=cells.get('place','');results.append(dict(number=n,rank=int(rank) if rank.isdigit() else None,status=rank))
    pay={}
    for line in root.xpath('//li[@class="win"]//div[@class="line"]'):
        n=line.xpath('./div[@class="num"]');v=line.xpath('./div[@class="yen"]')
        if n and v: pay[str(integer(txt(n[0])))]=integer(txt(v[0]))
    if not entrants: raise ValueError('no entrants '+str(path))
    return dict(race_id=f'JRA|{date}|{venue}|{number}',date=date,start=start,venue=venue,number=number,
        authority='JRA',surface=surface,distance=int(dist[1].replace(',','')),direction=direction,
        title=title,entrants=sorted(entrants,key=lambda h:h['number']),results=results,win_payouts=pay,
        source=str(path),source_kind='JRA_OFFICIAL_RACING_VIEWER_ARCHIVE')

def predictor_view(race):
    allowed=('race_id','date','start','venue','number','authority','surface','distance','direction','title','entrants')
    return {k:race[k] for k in allowed}
