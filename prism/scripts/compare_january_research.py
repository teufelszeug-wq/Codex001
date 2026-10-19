"""Local archived January comparison. Writes aggregate metrics only."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from prism_validation.compare import compare_runs, load_archived, load_b0
from prism_validation.experiments import archived_experts, chronological_calibration


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive-root', required=True)
    parser.add_argument('--b0', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--experiments', action='store_true')
    args = parser.parse_args()
    root = Path(args.archive_root)
    ordinal = load_archived(root/'ordinal_revalidated_v4')
    next_day = load_archived(root/'next_day_sensitivity_v4')
    b0 = load_b0(args.b0, ordinal)
    report = compare_runs({'archived_ordinal': ordinal, 'archived_next_day': next_day, 'b0_baseline': b0},
                          scope='ARCHIVED_JANUARY_RESEARCH_COMPARISON')
    if report['coverage']['paired_races'] != 1354:
        raise ValueError('January acceptance requires all 1354 paired races')
    path = Path(args.out); path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n'
    if path.exists() and path.read_text(encoding='utf-8') != content:
        raise ValueError('refuse differing report overwrite')
    path.write_text(content, encoding='utf-8')
    if args.experiments:
        extras = {'PHASE_D_EXPERT_PROBABILITIES.json': archived_experts(root/'ordinal_revalidated_v4',ordinal),
                  'PHASE_D_CHRONOLOGICAL_CALIBRATION.json': chronological_calibration(b0)}
        extras['PHASE_D_FEBRUARY_CALIBRATION_CANDIDATE.json'] = extras['PHASE_D_CHRONOLOGICAL_CALIBRATION.json']['frozen_artifact']
        for name, value in extras.items():
            target = path.parent/name
            text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n'
            if target.exists() and target.read_text(encoding='utf-8') != text:
                raise ValueError('refuse differing experiment overwrite')
            target.write_text(text, encoding='utf-8')
    print(json.dumps({'paired_races': report['coverage']['paired_races'], 'report_hash': report['report_hash'],
                      'runs': {k:{m:v[m] for m in ('log_loss','brier','profit_yen','effective_return_rate','max_drawdown_yen')}
                               for k,v in report['runs'].items()}}, indent=2))


if __name__ == '__main__':
    main()
