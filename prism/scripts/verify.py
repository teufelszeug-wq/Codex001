"""Run synthetic checks without pytest; optionally write a JSON report."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    log = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_audit_revision.py')
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    legacy = runpy.run_path(str(ROOT / 'tests/test_mdisc.py'))
    passed = []
    for name, fn in sorted(legacy.items()):
        if not name.startswith('test_'):
            continue
        if 'tmp_path' in fn.__code__.co_varnames[:fn.__code__.co_argcount]:
            with tempfile.TemporaryDirectory() as tmp:
                fn(Path(tmp))
        else:
            fn()
        passed.append(name)
    from prism_mdisc.core import DailyGate
    regression = DailyGate().evaluate([legacy['sample']()] * 35)
    assert regression['status'] == 'FAIL'
    assert regression['unique_sessions'] == 1
    assert regression['duplicate_sessions'] == 34
    assert regression['chars'] == 2891
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for directory in ('src', 'tests', 'scripts')
              for p in sorted((ROOT / directory).rglob('*.py'))}
    report = {'status': 'PASS' if result.wasSuccessful() else 'FAIL',
              'synthetic_only': True, 'new_tests': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'legacy_direct_tests': passed, 'duplicate_regression': regression,
              'source_sha256': hashes, 'training_achievement_verified': False,
              'production_deployed': False}
    print(log.getvalue(), file=sys.stderr)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    sys.exit(main())
