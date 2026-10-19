"""Run dated research comparison; write aggregates only, never raw entities."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from prism_validation.feature_replay import load_observations, run_experiment

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--january',required=True);p.add_argument('--bootstrap',required=True)
    p.add_argument('--database',required=True);p.add_argument('--out',required=True)
    p.add_argument('--models-out',help='Optional local-only complete model file; do not publish')
    a = p.parse_args()
    report, _, models = run_experiment(json.loads(Path(a.january).read_text()),
                                json.loads(Path(a.bootstrap).read_text()),load_observations(a.database))
    target = Path(a.out)
    data = json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if target.exists() and target.read_text() != data:
        raise ValueError('immutable aggregate output differs')
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():target.write_text(data)
    if a.models_out:
        model_target=Path(a.models_out)
        model_data=json.dumps(models,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
        if model_target.exists() and model_target.read_text()!=model_data:
            raise ValueError('immutable local models differ')
        if not model_target.exists():model_target.write_text(model_data)
    print(json.dumps({'report_hash':report['report_hash'],'training_races':report['training_races'],
                      'holdout_races':report['holdout_races'],'runs':{k:{m:v[m] for m in ('log_loss','brier','profit_yen','max_drawdown_yen')} for k,v in report['runs'].items()}},indent=2))
