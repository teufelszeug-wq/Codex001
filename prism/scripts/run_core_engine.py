"""Run an immutable one-race bundle. No network access or betting execution."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from prism_engine import predict,post_market,DEFAULT_CONFIG
from prism_engine.market import settle
from prism_engine.adapters import normalize

def write_immutable(path,value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n'
    if path.exists():
        if path.read_text(encoding='utf-8')!=raw:raise ValueError('refuse artifact overwrite: '+path.name)
    else:
        with path.open('x',encoding='utf-8') as f:f.write(raw)

def run(raw,market,locked_at,out,config=None,calibration=None,result=None):
    # All validation/computation completes before output files are committed.
    config=DEFAULT_CONFIG if config is None else config
    normalization=None
    if raw.get('schema')=='prism.engine.observations/v1':raw,normalization=normalize(raw)
    lock=predict(raw,locked_at,config,calibration)
    proposal=post_market(lock,market,config)
    bundle={'prediction':lock,'market_values':proposal,'training_achievement_verified':False,
            'production_deployed':False,'schema':'prism.engine.bundle/v1'}
    if normalization is not None:bundle['normalization']=normalization
    if result is not None:bundle['settlement']=settle(proposal['plan'],result,lock['race_id'],lock['cutoff'])
    directory=Path(out);directory.mkdir(parents=True,exist_ok=True)
    write_immutable(directory/'bundle.json',bundle)
    return bundle

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',required=True);p.add_argument('--market',required=True)
    p.add_argument('--locked-at',required=True);p.add_argument('--out',required=True)
    p.add_argument('--config');p.add_argument('--calibration');p.add_argument('--result');args=p.parse_args()
    read=lambda path:json.loads(Path(path).read_text(encoding='utf-8')) if path else None
    out=run(read(args.raw),read(args.market),args.locked_at,args.out,read(args.config),read(args.calibration),read(args.result))
    print(json.dumps({'prediction_hash':out['prediction']['lock_hash'],'mode':out['prediction']['mode'],
                      'decision':out['market_values']['plan']['decision'],'execution_allowed':False},indent=2))
