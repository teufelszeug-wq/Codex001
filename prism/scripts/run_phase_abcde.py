"""One-race A/B/C/E handoff with D evidence kept in a separate research track.

No network, betting, invented conversations or automatic model adoption. Supply
canonical observations, not evaluator datasets containing future results.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from prism_engine import predict, post_market, DEFAULT_CONFIG
from prism_engine.adapters import normalize
from prism_engine.contracts import digest
from prism_engine.market import settle
from prism_exchange import build_manifest, verify_manifest
from prism_dialogue import build_discussion_context, validate_discussion, review_learning
from prism_paper import render_paper


def _release_report(release):
    prediction = release['pre_bundle.json']['prediction']
    manifest = release['pre_manifest.json']
    audit = release['discussion_audit.json']
    report = {'schema': 'prism.cross-phase.release/v1', 'race_id': prediction['race_id'],
              'input_hash': prediction['input_hash'], 'prediction_hash': prediction['lock_hash'],
              'mode': prediction['mode'], 'pre_manifest_hash': manifest['manifest_hash'],
              'discussion_status': audit['status'], 'execution_allowed': False,
              'real_race_performance_validated': False, 'full_phase_abcde_complete': False,
              'production_deployed': False,
              'phase_d_scope': 'Independent coverage-matched research; not performance evidence for this race',
              'artifacts': {name: digest(value) for name, value in sorted(release.items()) if name != 'release.json'}}
    report['release_hash'] = digest(report)
    return report


def build_release(raw, market, locked_at, config=None, calibration=None,
                  discussion=None, result=None, learning_result=None, memory=None):
    """Validate every input before any writes; PRE is invariant under POST input."""
    config = DEFAULT_CONFIG if config is None else config
    raw = deepcopy(raw)
    normalization = None
    if raw.get('schema') == 'prism.engine.observations/v1':
        raw, normalization = normalize(raw)
    prediction = predict(raw, locked_at, config, calibration)
    proposal = post_market(prediction, market, config)
    bundle = {'schema': 'prism.engine.bundle/v1', 'prediction': prediction,
              'market_values': proposal, 'raw': raw,
              'training_achievement_verified': False, 'production_deployed': False}
    if normalization is not None:
        bundle['normalization'] = normalization
    context = build_discussion_context(bundle, memory=memory)
    artifacts = {'discussion_context': {'stage': 'PRE', 'payload': context}}
    release = {'pre_bundle.json': bundle, 'discussion_context.json': context}
    if memory is not None:
        artifacts['records_memory'] = {'stage': 'PRE', 'payload': memory}
        artifacts['discussion_context']['depends_on'] = ['records_memory']
        release['records_memory.json'] = memory
    if discussion is None:
        audit = {'status': 'NOT_EXECUTED', 'verified_independent_sessions': 0,
                 'training_achievement_verified': False}
        paper_discussion = None
    else:
        audit = validate_discussion(context, discussion)
        if audit['status'] != 'STRUCTURAL_PASS':
            raise ValueError('discussion rejected: ' + ','.join(audit['errors']))
        artifacts['discussion_records'] = {'stage': 'PRE', 'payload': discussion,
                                          'depends_on': ['discussion_context']}
        artifacts['discussion_audit'] = {'stage': 'PRE', 'payload': audit,
                                        'depends_on': ['discussion_records']}
        # Renderer receives only validated, prediction-bound records.
        paper_discussion = {**discussion, 'audit': audit}
        release['discussion_records.json'] = discussion
    release['discussion_audit.json'] = audit
    html = render_paper(bundle, discussion=paper_discussion)
    artifacts['paper'] = {'stage': 'PRE', 'payload': html,
                         'depends_on': sorted(artifacts)}
    manifest = build_manifest(bundle, artifacts)
    verify_manifest(manifest, bundle, artifacts)
    release.update({'paper.html': html, 'pre_manifest.json': manifest,
                    'pre_artifacts.json': artifacts})
    if learning_result is not None and discussion is None:
        raise ValueError('learning review requires actual supplied discussion records')
    if result is not None or learning_result is not None:
        post_bundle = deepcopy(bundle)
        post_artifacts = deepcopy(artifacts)
        if result is not None:
            settlement = settle(proposal['plan'], result, prediction['race_id'], prediction['cutoff'])
            post_bundle['settlement'] = settlement
            release['settlement.json'] = settlement
            post_artifacts['settlement'] = {'stage': 'POST', 'payload': settlement}
        if learning_result is not None:
            review = review_learning(context, discussion, learning_result)
            post_bundle['learning_review'] = review
            release['learning_review.json'] = review
            post_artifacts['learning_review'] = {'stage': 'POST', 'payload': review,
                                                'depends_on': ['discussion_records']}
        post_manifest = build_manifest(post_bundle, post_artifacts)
        # Result information cannot invalidate or rewrite any PRE cache entry.
        for kind, descriptor in manifest['artifacts'].items():
            if descriptor != post_manifest['artifacts'][kind]:
                raise ValueError('POST changed PRE artifact: ' + kind)
        release.update({'post_bundle.json': post_bundle, 'post_manifest.json': post_manifest,
                        'post_artifacts.json': post_artifacts})
    release['release.json'] = _release_report(release)
    return release


def verify_release(release):
    """Recheck mutable caller objects, identities and safe output names."""
    required = {'pre_bundle.json', 'discussion_context.json', 'discussion_audit.json',
                'paper.html', 'pre_manifest.json', 'pre_artifacts.json', 'release.json'}
    optional = {'discussion_records.json', 'settlement.json', 'learning_review.json',
                'post_bundle.json', 'post_manifest.json', 'post_artifacts.json', 'records_memory.json'}
    if not isinstance(release, dict) or not required <= set(release) or set(release) - required - optional:
        raise ValueError('release file set rejected')
    report = release['release.json']
    if report.get('release_hash') != digest({k: v for k, v in report.items() if k != 'release_hash'}):
        raise ValueError('release hash changed')
    if report.get('artifacts') != {name: digest(value) for name, value in sorted(release.items()) if name != 'release.json'}:
        raise ValueError('release artifact changed')
    if digest(report) != digest(_release_report(release)):
        raise ValueError('release identity/status/capability mismatch')
    bundle = release['pre_bundle.json']
    artifacts = release['pre_artifacts.json']
    context = build_discussion_context(bundle, memory=release.get('records_memory.json'))
    if digest(context) != digest(release['discussion_context.json']):
        raise ValueError('discussion context changed')
    expected = {'discussion_context': 'discussion_context.json', 'paper': 'paper.html'}
    if 'records_memory.json' in release:
        expected['records_memory'] = 'records_memory.json'
    if 'discussion_records.json' in release:
        records = release['discussion_records.json']
        audit = validate_discussion(context, records)
        if audit['status'] != 'STRUCTURAL_PASS' or digest(audit) != digest(release['discussion_audit.json']):
            raise ValueError('discussion audit changed')
        expected.update({'discussion_records': 'discussion_records.json', 'discussion_audit': 'discussion_audit.json'})
        discussion = {**records, 'audit': audit}
    else:
        if release['discussion_audit.json'] != {'status': 'NOT_EXECUTED', 'verified_independent_sessions': 0,
                                                'training_achievement_verified': False}:
            raise ValueError('unexecuted discussion status changed')
        discussion = None
    if set(artifacts) != set(expected) or any(digest(artifacts[k]['payload']) != digest(release[name]) for k, name in expected.items()):
        raise ValueError('PRE artifact/file binding mismatch')
    if render_paper(bundle, discussion=discussion) != release['paper.html']:
        raise ValueError('paper rendering changed')
    verify_manifest(release['pre_manifest.json'], bundle, artifacts)
    if report.get('pre_manifest_hash') != release['pre_manifest.json']['manifest_hash']:
        raise ValueError('release manifest binding changed')
    post_names = {'post_bundle.json', 'post_manifest.json', 'post_artifacts.json'}
    if set(release) & post_names:
        if not post_names <= set(release):
            raise ValueError('incomplete POST release')
        post = release['post_bundle.json']; post_artifacts = release['post_artifacts.json']
        expected_post = dict(expected)
        for kind in ('settlement', 'learning_review'):
            name = kind + '.json'
            if name in release:
                if digest(post.get(kind)) != digest(release[name]):
                    raise ValueError('POST bundle/file mismatch')
                expected_post[kind] = name
        if set(post_artifacts) != set(expected_post) or any(digest(post_artifacts[k]['payload']) != digest(release[n]) for k, n in expected_post.items()):
            raise ValueError('POST artifact/file binding mismatch')
        verify_manifest(release['post_manifest.json'], post, post_artifacts)
        for key, value in release['pre_manifest.json']['artifacts'].items():
            if value != release['post_manifest.json']['artifacts'].get(key):
                raise ValueError('POST changed PRE artifact')
    elif {'settlement.json', 'learning_review.json'} & set(release):
        raise ValueError('POST files require POST manifest')
    return True


def write_release(out, release):
    """Idempotent write; reject differing existing files before writing any file."""
    verify_release(release)
    out = Path(out)
    serialized = {name: value if name.endswith('.html') else
                  json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
                  for name, value in release.items()}
    for name, content in serialized.items():
        target = out / name
        if target.exists() and target.read_text(encoding='utf-8') != content:
            raise ValueError('refuse release overwrite: ' + name)
    out.mkdir(parents=True, exist_ok=True)
    for name, content in serialized.items():
        target = out / name
        if not target.exists():
            with target.open('x', encoding='utf-8') as handle:
                handle.write(content)
    return release['release.json']['release_hash']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('raw', 'market', 'locked-at', 'out'):
        parser.add_argument('--' + arg, required=True)
    for arg in ('config', 'calibration', 'discussion', 'result', 'learning-result'):
        parser.add_argument('--' + arg)
    memory_source = parser.add_mutually_exclusive_group()
    memory_source.add_argument('--records-db', help='Read the race DB once; freeze a conversation memo')
    memory_source.add_argument('--memory-file', help='Reuse a frozen as-of conversation memo')
    args = parser.parse_args()
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8')) if p else None
    raw = read(args.raw); discussion = read(args.discussion); memory = read(args.memory_file)
    if args.records_db:
        from prism_records import RecordStore
        from prism_records.memory import prepare_race_memory
        agents = sorted({'RIO', 'SHINOMIYA_RITSU', *(discussion or {}).get('required_agents', [])})
        store = RecordStore(args.records_db, read_only=True)
        try:
            memory = prepare_race_memory(store, raw['race']['race_id'], args.locked_at, agents)
        finally:
            store.close()
    release = build_release(raw, read(args.market), args.locked_at,
                            read(args.config), read(args.calibration), discussion,
                            read(args.result), read(args.learning_result), memory)
    write_release(args.out, release)
    print(json.dumps(release['release.json'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
