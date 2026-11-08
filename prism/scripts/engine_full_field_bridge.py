"""Bridge independently supplied, evidence-linked PRISM observations to the existing core engine.

Does not fetch official racecards, infer missing horse history, or attest provenance.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from prism_engine import predict
from prism_engine.adapters import normalize


def predict_full_field(observations, locked_at, horse_names, config=None):
    if observations.get('mode') == 'SYNTHETIC':
        mode = 'SYNTHETIC'
    elif observations.get('mode') == 'PRE_AVAILABLE':
        mode = 'PRE_AVAILABLE'
    else:
        raise ValueError('only SYNTHETIC or genuine PRE_AVAILABLE observations accepted')
    if observations.get('schema') == 'prism.engine.observations/v1':
        raw, _ = normalize(observations)
    else:
        raw = observations
    lock = predict(raw, locked_at, config)
    runners = raw['runners']
    ids = {r['horse_id'] for r in runners}
    if not isinstance(horse_names, dict) or set(horse_names) != ids:
        raise ValueError('all horse IDs require explicit names; no synthetic names inferred')
    numbers = [r['horse_no'] for r in runners]
    if len(set(numbers)) != len(numbers):
        raise ValueError('horse numbers ambiguous')
    diagnostics = []
    for runner in sorted(runners, key=lambda r:r['horse_no']):
        horse_id = runner['horse_id']
        name = horse_names[horse_id]
        if not isinstance(name,str) or not name.strip():
            raise ValueError('missing horse name')
        probability = lock['win'][horse_id]
        diagnostics.append({'horse_id':horse_id,'horse_no':runner['horse_no'],
                            'horse_name':name,'win_probability':probability,
                            'score':lock['scores'][horse_id],
                            'reason':'Core experimental score and probability; consult coverage and feature evidence',
                            'coverage':lock['coverage'][horse_id]})
    return {'schema':'prism.engine.full_field/v1','race_id':lock['race_id'],
            'mode':mode,'locked_at':locked_at,'model_version':lock['model_version'],
            'prediction_hash':lock['lock_hash'],'performance_validated':False,
            'source_authenticity_verified':False,'diagnoses':diagnostics,
            'note':'Model-generated quantitative diagnostics, not independent specialist opinions or actual betting recommendations.'}


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--observations',required=True)
    p.add_argument('--horse-names',required=True)
    p.add_argument('--locked-at',required=True)
    p.add_argument('--out',required=True)
    args = p.parse_args()
    observations = json.loads(Path(args.observations).read_text(encoding='utf-8'))
    names = json.loads(Path(args.horse_names).read_text(encoding='utf-8'))
    result = predict_full_field(observations,args.locked_at,names)
    out = Path(args.out)
    with out.open('x',encoding='utf-8') as f:
        json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write('\n')
    print(json.dumps({'race_id':result['race_id'],'runners':len(result['diagnoses']),
                      'mode':result['mode'],'prediction_hash':result['prediction_hash']}))


if __name__ == '__main__':
    main()
