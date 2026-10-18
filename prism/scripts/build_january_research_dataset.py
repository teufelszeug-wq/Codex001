"""Build a result-bearing evaluator dataset; never label it PRE-certified."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src/research'))
from archive_sources import jra_page,nar_archive
from b0_worker import digest

def month(cache,year,month,days):
    result=[]
    for day in days:
        folder=cache/f'{year}{month}{day}'
        expected={u.rsplit('/',1)[-1] for u in json.loads((folder/'links.json').read_text())}
        pages=sorted(folder.glob('*.htm'))
        if {p.name for p in pages}!=expected:raise ValueError('daily page coverage mismatch')
        parsed=[jra_page(p) for p in pages]
        if any(r['date']!=folder.name for r in parsed):raise ValueError('date mismatch')
        result+=parsed
    return result

def build(root,out):
    raw=Path(root)/'data/replay_202601/raw';out=Path(out);out.mkdir(parents=True,exist_ok=False)
    cache=raw/'jra_racingviewer'
    jan=month(cache,'2026','01',('04','05','10','11','12','17','18','24','25','31'))+nar_archive(raw/'nar_202601_official.zip')
    dec=month(cache,'2025','12',('06','07','13','14','20','21','27','28'))+nar_archive(raw/'nar_202512_official.zip')
    report={'mode':'EVALUATOR_RECONSTRUCTION_NOT_PIT','datasets':{}}
    for name,rows in [('january',jan),('bootstrap',dec)]:
        if len({r['race_id'] for r in rows})!=len(rows):raise ValueError('duplicate race')
        for r in rows:
            if len({h['number'] for h in r['entrants']})!=len(r['entrants']):raise ValueError('duplicate horse number')
        canonical=[{k:v for k,v in r.items() if k!='source'} for r in rows]
        (out/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
        report['datasets'][name]={'races':len(rows),'runners':sum(len(r['entrants']) for r in rows),
                                'canonical_hash':digest(canonical),'temporal_class':'UNKNOWN_TIMESTAMP'}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('out');a=p.parse_args()
    print(json.dumps(build(a.root,a.out),indent=2))
