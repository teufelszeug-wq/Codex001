"""Run scoped synthetic suites and a deterministic cross-phase handoff demo.

Counts are suite executions, not learning events, meetings, performance proof,
or unique historical assertions. Legacy recovery checks overlap engine tests.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts'), str(ROOT / 'tests/engine')]
from fixture import raw_fixture, market_fixture
from prism_engine import predict
from prism_engine.contracts import digest
from run_phase_abcde import build_release, write_release
from run_core_engine import write_immutable


def main(out, run_date='20261019', base_commit='fda857f7d7917d390c58a61702866a0ae7f36330'):
    if len(run_date) != 8 or not run_date.isdigit():
        raise ValueError('run_date must be YYYYMMDD')
    counts = {}
    passed = True
    for group in ('engine', 'exchange', 'dialogue', 'validation', 'model_readiness', 'research_models', 'paper', 'integration', 'records'):
        directory = ROOT / 'tests' / group
        if not directory.is_dir():
            raise ValueError('required test group missing: ' + group)
        log = io.StringIO()
        suite = unittest.TestLoader().discover(str(directory), pattern='test_*.py', top_level_dir=str(directory))
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        print(log.getvalue(), file=sys.stderr)
        counts[group] = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors)}
        passed = passed and result.wasSuccessful() and result.testsRun > 0
    raw = raw_fixture(); when = '2026-01-01T09:55:00+09:00'
    market = market_fixture(predict(raw, when))
    a = build_release(raw, market, when)
    b = build_release(raw, market, when)
    if a != b:
        raise ValueError('cross-phase deterministic replay failed')
    with tempfile.TemporaryDirectory() as directory:
        first = write_release(Path(directory)/'a', a)
        write_release(Path(directory)/'b', b)
        write_release(Path(directory)/'a', a)
        for name in a:
            if (Path(directory)/'a'/name).read_bytes() != (Path(directory)/'b'/name).read_bytes():
                raise ValueError('cross-phase byte replay failed: ' + name)
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for directory in ('src', 'tests', 'scripts')
                     for p in sorted((ROOT / directory).rglob('*.py'))}
    report = {'schema': 'prism.cross-phase.acceptance/v1', 'status': 'PASS' if passed else 'FAIL',
              'base_commit': base_commit,
              'synthetic_only': True, 'test_groups': counts,
              'test_count_scope': 'Scoped suite executions, not learning counts; legacy recovery checks overlap engine',
              'determinism': 'Independent builds and serialized releases byte-identical; idempotent replay',
              'demo_release_hash': first, 'prediction_hash': a['release.json']['prediction_hash'],
              'source_sha256': source_hashes, 'verified_independent_sessions': 0,
              'paper_visual_qa': 'NOT_PART_OF_THIS_UNIT_TEST_REPORT',
              'performance_validated': False, 'full_phase_abcde_complete': False,
              'strict_pit_certified': False, 'production_deployed': False}
    report['report_hash'] = digest(report)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    write_immutable(out / ('PHASE_ABCDE_ACCEPTANCE_'+run_date+'.json'), report)
    write_immutable(out / ('PHASE_ABCDE_SYNTHETIC_RELEASE_'+run_date+'.json'), a['release.json'])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--out', required=True)
    parser.add_argument('--run-date', default='20261019')
    parser.add_argument('--base-commit', default='fda857f7d7917d390c58a61702866a0ae7f36330')
    args = parser.parse_args()
    sys.exit(main(args.out, args.run_date, args.base_commit))
