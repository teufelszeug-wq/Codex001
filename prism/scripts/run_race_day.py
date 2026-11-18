"""Preserve official race forecasts, race-day changes and post-race results."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
import fcntl
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from discover_official_races import discover_jra, discover_nar, nar_result_url
from fetch_official_result import fetch as fetch_result
from jra_forecast_card import JST
from run_forecast_batch import read_json, run as forecast_batch, run_panel, save_bytes_once, save_input, target, validate_panel_output

OPERATIONS = Path(__file__).parent
RACE_ID = re.compile(r'\d{8}-(?:JRA|NAR)-[A-Z]+-\d{2}')
VERSIONS = re.compile(r'v([2-9]|[1-9]\d+)\.json')
RECOVERABLE = (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError)
# Preserve editorial sidecars and prior audit evidence across archive cycles.
ROOT_SIDECARS = frozenset({'cycle-report.json', 'forecast-index.md'})
STATE_FILE = re.compile(
    r'(?:racecard(?:-v\d+)?|v\d+(?:-racecard)?|declarations-(?:racecard|v1|roundtable-v1)'
    r'|roundtable-v1|official-result|settlement|post-race-review)\.json'
)


def saved_races(history):
    return sorted(path for path in history.iterdir() if path.is_dir() and RACE_ID.fullmatch(path.name))


def restore_history(history, archive):
    with ZipFile(archive) as package:
        for info in package.infolist():
            name = PurePosixPath(info.filename)
            valid_race = (len(name.parts) == 2 and RACE_ID.fullmatch(name.parts[0]) and name.name.endswith(('.json', '.md', '.txt')))
            valid_root = (len(name.parts) == 1 and name.name in ROOT_SIDECARS)
            valid_audit = (len(name.parts) == 2 and name.parts[0] == 'audit' and name.name.endswith('.json'))
            if not (valid_race or valid_root or valid_audit) or '..' in name.parts:
                continue
            if info.file_size > 12_000_000:
                raise ValueError(f'oversized history record: {name}')
            path = history.joinpath(*name.parts)
            path.parent.mkdir(exist_ok=True)
            data = package.read(info)
            if save_bytes_once(path, data) != data:
                raise ValueError(f'history archive disagrees with the saved record: {name}')


def export_history(history, archive, report):
    with ZipFile(archive, 'x', compression=ZIP_DEFLATED) as package:
        for directory in saved_races(history):
            for path in sorted(directory.iterdir()):
                if path.is_file() and path.suffix in {'.json', '.md', '.txt'}:
                    package.write(path, path.relative_to(history))
        audit = history / 'audit'
        if audit.is_dir():
            for path in sorted(audit.glob('*.json')):
                if path.is_file():
                    package.write(path, path.relative_to(history))
        for filename in ROOT_SIDECARS - {'cycle-report.json'}:
            sidecar = history / filename
            if sidecar.is_file():
                package.write(sidecar, filename)
        package.writestr('cycle-report.json', json.dumps(report, ensure_ascii=False, indent=2) + '\n')


def latest_edition(directory):
    versions = [int(match[1]) for path in directory.glob('v*.json') if (match := VERSIONS.fullmatch(path.name))]
    if not versions:
        return None
    number = max(versions)
    forecast = read_json(directory / f'v{number}.json')
    if forecast['version'] != number or forecast['race_id'] != directory.name or forecast['metadata']['phase'] not in {'FINAL', 'UPDATE'}:
        raise ValueError('saved final forecast identity mismatch')
    saved = datetime.fromisoformat(forecast['saved_at'])
    off = datetime.fromisoformat(forecast['off_at'])
    if saved.tzinfo is None or off.tzinfo is None or not saved < off or saved > datetime.now(JST):
        raise ValueError('saved forecast timestamp is outside the pre-race window')
    return forecast


def official_jra_seeds(history, days, filename, url_field):
    selected = {day.strftime('%Y%m%d') for day in days}
    seeds = {}
    for directory in saved_races(history):
        path = directory / filename
        meeting = directory.name.rsplit('-', 1)[0]
        if '-JRA-' in meeting and directory.name[:8] in selected and path.is_file():
            if meeting not in seeds or directory.name.endswith('-11'):
                seeds[meeting] = read_json(path)[url_field]
    return list(seeds.values())


def active_history(history, days, today, lookback):
    floor = (today - timedelta(days=lookback)).strftime('%Y%m%d')
    requested = {day.strftime('%Y%m%d') for day in days}
    ceiling = today.strftime('%Y%m%d')
    return [path for path in saved_races(history)
            if path.name[:8] in requested or floor <= path.name[:8] <= ceiling]


def race_day_changes(before, card):
    # A horse identity change is not an ordinary odds/track-condition update.
    # Stop before issuing a new forecast and require an official identity review.
    previous_names = {row['horse_no']: row['horse_name'] for row in before['runners']}
    current_names = {row['horse_no']: row['horse_name'] for row in card['runners'] if row['status'] not in {'SCRATCHED', 'EXCLUDED'}}
    for number in previous_names.keys() & current_names.keys():
        if previous_names[number] != current_names[number]:
            raise ValueError(f'official runner identity mismatch at horse {number}: {previous_names[number]} != {current_names[number]}')
    previous_active = {row['horse_no']: row.get('jockey_name') for row in before['runners']}
    active = [row for row in card['runners'] if row['status'] not in {'SCRATCHED', 'EXCLUDED'}]
    old_metadata = before['metadata']
    return (
        previous_active != {row['horse_no']: row.get('jockey_name') for row in active}
        or datetime.fromisoformat(before['off_at']) != datetime.fromisoformat(card['off_at'])
        or (card.get('track_condition') is not None and old_metadata.get('track_condition') != card['track_condition'])
        or any(
            row.get(field) is not None and row[field] != old_metadata.get(map_name, {}).get(str(row['horse_no']))
            for row in active for field, map_name in (('body_weight', 'body_weights'), ('win_odds', 'win_odds'))
        )
    )


def refresh_one(history, directory, previous, url):
    path = directory / f'racecard-v{previous["version"] + 1}.json'
    if path.exists():
        card = read_json(path)
    else:
        _, fetch = target(url, previous_runners=previous['metadata'].get('entry_status', ()))
        card = fetch()
        if not race_day_changes(previous, card):
            return {'race_id': directory.name, 'status': 'UNCHANGED', 'version': previous['version']}
        save_input(path, card)
    backend = previous['metadata']['model_backend']
    model = 'local' if backend == 'local_rules' else 'openai'
    result = run_panel(history, path, model, previous['version'])
    validate_panel_output(result, directory.name, card, 'UPDATE')
    return {'race_id': directory.name, 'status': 'UPDATED', 'version': result['version'],
            'saved_at': result['saved_at'], 'changes': result['changes']}


def settle_one(directory, previous, result_url):
    result_path = directory / 'official-result.json'
    output = directory / 'settlement.json'
    if not result_path.exists():
        if '-NAR-' in directory.name:
            for source in previous['source_refs']:
                try:
                    identity, _ = target(source)
                    if identity == directory.name:
                        result_url = nar_result_url(source)
                        break
                except ValueError:
                    continue
        if not result_url:
            return {'race_id': directory.name, 'status': 'AWAITING_OFFICIAL_RESULT_URL'}
        save_input(result_path, fetch_result(result_url))
    official = read_json(result_path)
    if output.exists():
        settlement = read_json(output)
        if (settlement['forecast_sha256'] != previous['content_sha256'] or
                settlement['official_result_source_sha256'] != official['source_sha256']):
            raise ValueError('settlement does not match saved forecast and result')
    else:
        subprocess.run(['node', str(OPERATIONS / 'settle_forecast.mjs'), '--forecast',
                        str(directory / f'v{previous["version"]}.json'), '--result', str(result_path),
                        '--out', str(output)], capture_output=True, text=True, timeout=60, check=True)
        settlement = read_json(output)
    review_path = directory / 'post-race-review.json'
    if not review_path.exists():
        save_input(review_path, review_race(previous, official, settlement))
    return {'race_id': directory.name, 'status': 'SETTLED', 'version': previous['version'],
            'forecasters': len(settlement['summary'])}


def review_race(forecast, result, settlement):
    finishers = {row['horse_no']: row for row in result['finishers']}
    winners = [row for row in finishers.values() if row['finish'] == 1]
    review = []
    for forecast_row, paid in zip(forecast['records'], settlement['summary'], strict=True):
        if forecast_row['forecaster_id'] != paid['forecaster_id']:
            raise ValueError('post-race reviewer does not match settlement')
        top = next((row for row in forecast_row['picks'] if row['mark'] == '◎'), None)
        result_top = finishers[top['horse_no']] if top else None
        marks = {row['horse_no']: row['mark'] for row in forecast_row['picks']}
        scores = {row['horse_no']: row.get('score') for row in forecast_row['diagnoses']}
        review.append({
            'forecaster_id': forecast_row['forecaster_id'], 'name': forecast_row['display_name'],
            'execution_id': forecast_row['execution_id'], 'top_pick_result': result_top,
            'winners': [{**winner, 'mark': marks.get(winner['horse_no']), 'score': scores.get(winner['horse_no'])}
                        for winner in winners],
            'skip_reason': forecast_row['skip_reason'], 'stake_yen': paid['stake_yen'],
            'payout_yen': paid['payout_yen'], 'profit_yen': paid['profit_yen'],
        })
    return {'schema': 'prism.post_race_review/v1', 'race_id': forecast['race_id'], 'forecast_version': forecast['version'],
            'forecast_sha256': forecast['content_sha256'], 'result_source_sha256': result['source_sha256'],
            'reviewed_at': datetime.now(JST).isoformat(), 'forecasters': review}


def prior_result_urls(history, due, seeds):
    missing = [(path, version) for path, version in due
               if '-JRA-' in path.name and not (path / 'official-result.json').exists()]
    dates = {datetime.fromisoformat(version['off_at']).astimezone(JST).date() for _, version in missing}
    if not dates:
        return {}, []
    anchors = [*seeds, *official_jra_seeds(history, dates, 'official-result.json', 'official_source')]
    return discover_jra(dates, anchors, result=True)


def collect_jobs(jobs, errors):
    output = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for race, future in [(race, pool.submit(operation, *arguments)) for race, operation, arguments in jobs]:
            try:
                output.append(future.result())
            except RECOVERABLE as error:
                errors.append({'race_id': race, 'error': getattr(error, 'stderr', '') or str(error)})
    return output


def run(history, days, *, model, card_seeds, result_seeds, mode, lookback):
    now = datetime.now(JST)
    today = now.date()
    errors, discovery_errors, updates, settlements = [], [], [], []
    activity = {'finalized': 0, 'declarations': 0, 'races': [], 'errors': []}
    urls = {}
    existing = {}
    for directory in active_history(history, days, today, lookback):
        try:
            if version := latest_edition(directory):
                existing[directory.name] = (directory, version)
        except RECOVERABLE as error:
            errors.append({'race_id': directory.name, 'error': str(error)})
    if mode != 'settle':
        card_seeds = [*card_seeds, *official_jra_seeds(history, days, 'racecard.json', 'official_url')]
        with ThreadPoolExecutor(max_workers=2) as pool:
            jra = pool.submit(discover_jra, days, card_seeds)
            nar = pool.submit(discover_nar, [day for day in days if day <= today + timedelta(days=1)])
            for future in (jra, nar):
                discovered, problems = future.result()
                urls.update(discovered)
                discovery_errors.extend(problems)
        activity = forecast_batch(history, [url for race, url in urls.items() if race not in existing], model=model)
        # Only races that already had an official final before this cycle need a fresh input capture.
        updates = collect_jobs([
            (race, refresh_one, (history, path, version, urls[race]))
            for race, (path, version) in sorted(existing.items(), key=lambda row: datetime.fromisoformat(row[1][1]['off_at']))
            if race[:8] == today.strftime('%Y%m%d') and race in urls and datetime.fromisoformat(version['off_at']) > now
        ], errors)
    if mode != 'forecast':
        due = [(path, version) for path, version in existing.values() if datetime.fromisoformat(version['off_at']) < now]
        jra_results, problems = prior_result_urls(history, due, result_seeds)
        discovery_errors.extend(problems)
        settlements = collect_jobs([
            (path.name, settle_one, (path, version, jra_results.get(path.name)))
            for path, version in due
        ], errors)
    return {'generated_at': datetime.now(JST).isoformat(), 'dates': [day.isoformat() for day in days],
            'discovered': len(urls), 'already_final': sorted(set(urls) & existing.keys()),
            'forecast': activity, 'updates': updates, 'settlements': settlements,
            'discovery_errors': discovery_errors, 'errors': errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--date', action='append', type=date.fromisoformat)
    parser.add_argument('--jra-card-seed', action='append', default=[])
    parser.add_argument('--jra-result-seed', action='append', default=[])
    parser.add_argument('--mode', choices=['all', 'forecast', 'settle'], default='all')
    parser.add_argument('--model', choices=['local', 'openai'], default='local')
    parser.add_argument('--settle-lookback', type=int, default=7)
    parser.add_argument('--restore', action='append', type=Path, default=[])
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    if args.settle_lookback < 0:
        parser.error('settle lookback cannot be negative')
    today = datetime.now(JST).date()
    horizon = {3: 3, 4: 2}.get(today.weekday(), 1)
    days = sorted(set(args.date or [today + timedelta(days=offset) for offset in range(horizon + 1)]))
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / '.race-day.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for archive in args.restore:
            restore_history(args.out, archive)
        report = run(args.out, days, model=args.model, card_seeds=args.jra_card_seed,
                     result_seeds=args.jra_result_seed, mode=args.mode, lookback=args.settle_lookback)
        if args.archive:
            export_history(args.out, args.archive, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report['errors'] or report['discovery_errors'] or report['forecast']['errors']))


if __name__ == '__main__':
    sys.exit(main())
