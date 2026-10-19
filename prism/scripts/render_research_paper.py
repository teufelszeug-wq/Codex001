"""Create a private, held-out-race research paper; never uploads raw records."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from prism_validation.feature_replay import load_observations, build_rows, research_paper_dto
from prism_paper import render_research_paper


def main():
    p=argparse.ArgumentParser()
    for name in ('january','bootstrap','database','report','models','out'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--race-id'); a=p.parse_args()
    january=json.loads(Path(a.january).read_text())
    report=json.loads(Path(a.report).read_text())
    rows=build_rows(january,json.loads(Path(a.bootstrap).read_text()),load_observations(a.database))
    row=next(r for r in rows if report['holdout_dates'][0] <= r['date'] <= report['holdout_dates'][1] and (not a.race_id or r['race_id']==a.race_id))
    race=next(r for r in january if r['race_id']==row['race_id'])
    models=json.loads(Path(a.models).read_text())
    dto=research_paper_dto(race,row,models['plus_both'],a.database)
    html=render_research_paper(dto,report)
    target=Path(a.out).resolve()
    if target == Path(__file__).resolve().parents[1] or Path(__file__).resolve().parents[1] in target.parents:
        raise ValueError('actual-race paper output must be outside public repository')
    target.mkdir(parents=True,exist_ok=True)
    (target/'research_race.json').write_text(json.dumps(dto,ensure_ascii=False,indent=2)+'\n')
    (target/'PRISM_JANUARY_RESEARCH.html').write_text(html)
    print(json.dumps({'race_id':dto['race_id'],'runners':len(dto['runners']),'pages':4,'html':str(target/'PRISM_JANUARY_RESEARCH.html')},ensure_ascii=False))


if __name__=='__main__':main()
