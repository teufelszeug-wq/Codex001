"""CLI and persistent worker. Explicit job inputs never imply race coverage."""
import argparse
from datetime import datetime, timezone
import json
import importlib.util
import os
from pathlib import Path
import signal
import shutil
import sys
import threading

from prism_engine.contracts import digest, timestamp
from .store import Store, utcnow


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def execute_job(job, store, *, provider=None, now=utcnow):
    from .provider import OpenAIProvider
    from .workflow import operation_race, run_pre_day
    from .characters import build_character_snapshot
    required = {'race_id', 'card', 'characters', 'engine_input'}
    if not isinstance(job, dict) or not required <= set(job):
        raise ValueError('job requires race_id/card/characters/engine_input')
    race_id = Store.safe(job['race_id'])
    edition = Store.safe(job.get('edition', 'pre-v1'))
    published = store.get(race_id, 'publication', edition)
    if published:
        return {'race_id': race_id, 'status': 'SKIPPED_PUBLISHED'}
    if job.get('due_at') and timestamp(now()) < timestamp(job['due_at']):
        return {'race_id': race_id, 'status': 'NOT_DUE'}
    try:
        source = read_json(job['characters'])
        snapshot = (source if source.get('schema') == 'prism.characters.snapshot/v1'
                    else build_character_snapshot(source['records'], source_url=source['source_url'],
                                                   captured_at=source['captured_at']))
        card = read_json(job['card'])
        if card['race_id'] != race_id:
            raise ValueError('JOB_RACE_ID_MISMATCH')
        race = operation_race(card, snapshot)
        if timestamp(now()) >= timestamp(race['start_at']):
            raise ValueError('DEADLINE_PASSED_NO_BACKDATING')
        execution = run_pre_day(race, snapshot, read_json(job['engine_input']), store,
                    provider or OpenAIProvider(), edition=edition, now=now,
                    render=job.get('render', True))
        return {'race_id': race_id, 'status': 'AWAITING_VISUAL_QA' if execution['paper'] else 'EXECUTED'}
    except Exception as exc:
        # HTTP credentials are never logged; provider errors expose only codes.
        reason = type(exc).__name__ + ': ' + str(exc)[:300]
        store.status(race_id, 'BLOCKED', {'reason': reason, 'official_publications': 0})
        return {'race_id': race_id, 'status': 'BLOCKED', 'reason': reason}


def tick(config, store, *, provider=None, now=utcnow):
    if not isinstance(config, dict):
        raise ValueError('configuration object required')
    configured_jobs = config.get('jobs', [])
    watches = config.get('watches', [])
    if not isinstance(configured_jobs, list) or not isinstance(watches, list):
        raise ValueError('jobs and watches must be lists')
    jobs = list(configured_jobs)
    for entry in [*jobs, *watches]:
        if not isinstance(entry, dict):
            raise ValueError('each job/watch must be an object')
        Store.safe(entry.get('race_id'))
    watch_results = []
    for watch in watches:
        from .acquisition import prepare_watch
        try:
            prepared = prepare_watch(watch, store, now=now)
            if prepared.get('status') == 'NOT_DUE':
                watch_results.append(prepared)
            else:
                jobs.append(prepared)
        except Exception as exc:
            race_id = Store.safe(watch['race_id'])
            reason = type(exc).__name__ + ': ' + str(exc)[:300]
            store.status(race_id, 'BLOCKED_ACQUISITION', {'reason': reason})
            watch_results.append({'race_id': race_id, 'status': 'BLOCKED', 'reason': reason})
    if len({job.get('race_id') for job in jobs}) != len(jobs):
        raise ValueError('duplicate race jobs')
    # A missing or invalid timestamp remains an actionable blocker per job.
    def order(job):
        return job.get('due_at', '')
    results = watch_results + [execute_job(job, store, provider=provider, now=now)
               for job in sorted(jobs, key=order)]
    settlement_jobs = config.get('settlements', [])
    if not isinstance(settlement_jobs, list):
        raise ValueError('settlements must be a list')
    for job in settlement_jobs:
        if not isinstance(job, dict):
            raise ValueError('each settlement job must be an object')
        Store.safe(job.get('race_id'))
        from .aftercare import process_settlement_job
        results.append(process_settlement_job(job, store, provider=provider, now=now))
    return {'schema': 'prism.ops.tick/v1', 'observed_at': now(), 'configured_races': len(jobs),
            'official_race_universe_verified': False,
            'results': results, 'blocked': sum(r['status'] in {'BLOCKED', 'SETTLED_REFLECTION_BLOCKED'} for r in results),
            'production_deployed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True, help='private persistent volume')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('run', 'worker'):
        child = commands.add_parser(name)
        child.add_argument('--config', required=True)
    commands.add_parser('status')
    commands.add_parser('doctor')
    approve = commands.add_parser('publish')
    approve.add_argument('--race-id', required=True)
    approve.add_argument('--edition', default='pre-v1')
    approve.add_argument('--qa-manifest', required=True,
                         help='manifest signed after inspecting every PDF/PNG page')
    settle = commands.add_parser('settle')
    settle.add_argument('--race-id', required=True)
    settle.add_argument('--edition', default='pre-v1')
    settle.add_argument('--result', required=True)
    settle.add_argument('--reflect', action='store_true')
    delta = commands.add_parser('delta')
    delta.add_argument('--race-id', required=True)
    delta.add_argument('--base-edition', default='pre-v1')
    delta.add_argument('--version', required=True)
    delta.add_argument('--input', required=True, help='changes/change_reason/source_snapshot JSON')
    delta_paper = commands.add_parser('delta-paper')
    delta_paper.add_argument('--race-id', required=True)
    delta_paper.add_argument('--version', required=True)
    delta_publish = commands.add_parser('delta-publish')
    delta_publish.add_argument('--race-id', required=True)
    delta_publish.add_argument('--version', required=True)
    delta_publish.add_argument('--qa-manifest', required=True)
    collect = commands.add_parser('collect')
    collect.add_argument('--url', required=True)
    collect.add_argument('--authority', choices=('JRA', 'NAR'), required=True)
    collect.add_argument('--date', required=True)
    collect.add_argument('--venue', required=True)
    collect.add_argument('--race-no', required=True, type=int)
    collect.add_argument('--race-name')
    collect.add_argument('--result', action='store_true')
    discover = commands.add_parser('discover')
    discover.add_argument('--authority', choices=('JRA', 'NAR'), required=True)
    discover.add_argument('--date', action='append', required=True)
    discover.add_argument('--seed', action='append', default=[])
    discover.add_argument('--max-pages', type=int, default=80)
    discover.add_argument('--result', action='store_true')
    args = parser.parse_args(argv)
    store = Store(args.data)
    try:
        if args.command == 'status':
            report = {'jobs': store.jobs()}
        elif args.command == 'doctor':
            checks = {
                'OPENAI_API_KEY': bool(os.environ.get('OPENAI_API_KEY', '').strip()),
                'PRISM_OPENAI_MODEL': bool(os.environ.get('PRISM_OPENAI_MODEL', '').strip()),
                'chromium': bool(shutil.which('chromium')),
                'node': bool(shutil.which('node')),
                'playwright': importlib.util.find_spec('playwright') is not None,
                'PyMuPDF': importlib.util.find_spec('pymupdf') is not None,
            }
            report = {'schema': 'prism.ops.readiness/v1', 'checks': checks,
                      'blocked': sum(not value for value in checks.values()),
                      'missing': [key for key, value in checks.items() if not value],
                      'persistent_signing_key_configured': bool(os.environ.get('PRISM_RECEIPT_SIGNING_KEY')),
                      'independent_api_executed': False, 'production_deployed': False}
        elif args.command == 'publish':
            from .workflow import publish_saved
            report = publish_saved(store, args.race_id, read_json(args.qa_manifest), edition=args.edition)
        elif args.command == 'settle':
            from .postrace import settle_saved, reflect_saved
            report = settle_saved(store, args.race_id, read_json(args.result), edition=args.edition)
            if args.reflect:
                from .provider import OpenAIProvider
                report['reflection'] = reflect_saved(store, args.race_id, OpenAIProvider(), edition=args.edition)
        elif args.command == 'delta':
            from .daydelta import apply_day_delta
            from .provider import OpenAIProvider
            document = read_json(args.input)
            report = apply_day_delta(store, args.race_id, document['changes'],
                document['change_reason'], document['source_snapshot'], OpenAIProvider(),
                version=args.version, base_edition=args.base_edition)
        elif args.command == 'delta-paper':
            from .daydelta import render_day_delta
            report = render_day_delta(store, args.race_id, version=args.version)
        elif args.command == 'delta-publish':
            from .daydelta import publish_day_delta
            report = publish_day_delta(store, args.race_id, read_json(args.qa_manifest), version=args.version)
        elif args.command == 'discover':
            from .discovery import discover_official_races
            report = discover_official_races(args.authority, args.date,
                store.directory / 'official-discovery', seeds=args.seed, result=args.result,
                max_pages=args.max_pages)
            store.save('DISCOVERY-' + args.authority, 'discovery', digest(report), report)
        elif args.command == 'collect':
            from .official import fetch_official_snapshot, parse_nar_racecard, parse_nar_result, parse_jra_racecard, parse_jra_result
            source = fetch_official_snapshot(args.url, store.directory / 'official-sources')
            if args.authority == 'NAR':
                function = parse_nar_result if args.result else parse_nar_racecard
                report = function(source, expected_date=args.date, expected_venue=args.venue,
                                  expected_race_no=args.race_no)
            else:
                function = parse_jra_result if args.result else parse_jra_racecard
                report = function(source, expected_date=args.date, expected_venue=args.venue,
                            expected_race_no=args.race_no, expected_race_name=args.race_name)
            receipt = store.save(report['race_id'], 'official-result' if args.result else 'racecard',
                                 digest(report), report)
            report = {'record': report, 'artifact': receipt}
        elif args.command == 'run':
            report = tick(read_json(args.config), store)
        else:
            stopped = threading.Event()
            for name in (signal.SIGINT, signal.SIGTERM):
                signal.signal(name, lambda *_: stopped.set())
            while not stopped.is_set():
                config = read_json(args.config)
                report = tick(config, store)
                print(json.dumps(report, ensure_ascii=False), flush=True)
                interval = config.get('poll_seconds', 60)
                if type(interval) is not int or not 10 <= interval <= 3600:
                    raise ValueError('poll_seconds must be an integer within 10..3600')
                stopped.wait(interval)
            return 0
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if report.get('blocked') or report.get('ready') is False else 0
    finally:
        store.close()


if __name__ == '__main__':
    sys.exit(main())
