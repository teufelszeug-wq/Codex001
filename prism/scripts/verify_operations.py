"""Run every Python test directory in isolation and both Node suites.

Report software executions only, never model predictions or live race success.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'src'), str(ROOT / 'scripts'),
                                       str(ROOT / 'tests' / 'engine')))
    groups = [ROOT / 'tests', *sorted(p for p in (ROOT / 'tests').iterdir() if p.is_dir() and p.name != '__pycache__')]
    commands = [(str(p.relative_to(ROOT)), [sys.executable, '-m', 'unittest', 'discover',
                 '-s', str(p), '-p', 'test_*.py', '-v']) for p in groups
                if list(p.glob('test_*.py'))]
    commands.append(('legacy-audit', [sys.executable, 'scripts/verify.py']))
    node_tests = sorted(str(p.relative_to(ROOT)) for folder in ('foundation', 'operations')
                        for p in (ROOT / 'tests' / folder).glob('*.test.mjs'))
    node_tests += sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'tests').glob('*.test.mjs'))
    commands.append(('node', ['node', '--test', '--test-reporter=tap', *node_tests]))
    output = Path(args.out); output.mkdir(parents=True, exist_ok=False)
    reports = []
    for group, command in commands:
        run = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
        log = run.stdout + run.stderr
        log_path = output / (group.replace('/', '-') + '.log')
        log_path.write_text(log, encoding='utf-8')
        counts = re.findall(r'Ran (\d+) tests?', log)
        node_counts = re.findall(r'# tests (\d+)', log)
        count = int((node_counts or counts or ['0'])[-1])
        # Legacy verifier also runs direct function assertions and is checked by
        # its process result; unittest groups must actually collect tests.
        skipped = [int(value) for value in re.findall(r'\bskipped[= ](\d+)', log)]
        passed = run.returncode == 0 and (count > 0 or group == 'legacy-audit') and not any(skipped)
        reports.append({'group': group, 'exit_code': run.returncode, 'tests_run': count,
                        'passed': passed, 'log': log_path.name,
                        'skipped': skipped})
        print(json.dumps(reports[-1]), flush=True)
        if not passed:
            print(log[-8000:], file=sys.stderr)
    source_files = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
                    for folder in ('src', 'scripts', 'tests')
                    for p in sorted((ROOT / folder).rglob('*'))
                    if p.is_file() and p.suffix in {'.py', '.mjs'}}
    report = {'schema': 'prism.ops.software_verification/v1',
              'observed_at': datetime.now(timezone.utc).isoformat(), 'groups': reports,
              'passed': all(r['passed'] for r in reports),
              'source_file_count': len(source_files),
              'source_tree_sha256': sha256(json.dumps(source_files, sort_keys=True).encode()).hexdigest(),
              'count_scope': 'suite executions; root discovery may repeat package tests',
              'independent_model_executions': 0, 'live_pre_day_publications': 0,
              'official_forward_settlements': 0, 'production_deployed': False}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
