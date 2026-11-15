"""Run a supplied list of official racecards in scheduled post-time order."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit

from fetch_jra_racecard import fetch_for_forecast as fetch_jra, racecard_identity as jra_identity
from fetch_nar_racecard import fetch_for_forecast as fetch_nar, racecard_identity as nar_identity, VENUES

PANEL = Path(__file__).with_name('run_forecast_panel.mjs')


def target(url, *, previous_runners=()):
    host = urlsplit(url).hostname
    if host in {'jra.go.jp', 'www.jra.go.jp'}:
        date, _, venue, _, _, race = jra_identity(url)
        return f'{date}-JRA-{venue}-{race:02d}', lambda: fetch_jra(url, allow_unframed=True, previous_runners=previous_runners)
    if host == 'www.keiba.go.jp':
        date, venue, race = nar_identity(url)
        return f'{date.replace("-", "")}-NAR-{VENUES[venue][1]}-{race:02d}', lambda: fetch_nar(url)
    raise ValueError('official JRA or NAR racecard URL required')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save_bytes_once(path, data):
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        if temporary is not None:
            temporary.unlink()
    return path.read_bytes()


def save_input(path, card):
    data = (json.dumps(card, ensure_ascii=False) + '\n').encode('utf-8')
    return json.loads(save_bytes_once(path, data))


def prepare(directory, url):
    race, fetch = target(url)
    race_dir = directory / race
    race_dir.mkdir(parents=True, exist_ok=True)
    numbered = race_dir / 'racecard.json'
    early = race_dir / 'declarations-racecard.json'
    if numbered.exists():
        card = read_json(numbered)
    elif early.exists() and not (race_dir / 'declarations-roundtable-v1.json').exists():
        card = read_json(early)
    else:
        try:
            card = fetch()
        except OSError:
            if not early.exists():
                raise
            card = read_json(early)
        path = early if card.get('entry_stage') == 'DECLARATIONS' else numbered
        if card['race_id'] != race:
            raise ValueError('racecard identity changed')
        card = save_input(path, card)
    if card['race_id'] != race:
        raise ValueError('saved racecard identity mismatch')
    return race, card


def run_panel(directory, card_path, model, update_from=None):
    arguments = ['node', str(PANEL), '--card', str(card_path), '--out', str(directory), '--model', model]
    if update_from is not None:
        arguments.extend(('--update-from', str(update_from)))
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=600, check=False)
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or 'forecast command failed')
    return json.loads(result.stdout)


def validate_panel_output(value, race, card, expected_phase):
    # A successful subprocess is not evidence of a completed forecast.
    forecasts = value.get('forecasts')
    if not isinstance(forecasts, list) or not forecasts:
        raise ValueError('forecast output has no forecaster records')
    if not value.get('saved_at'):
        raise ValueError('forecast output has no saved_at')
    if value.get('race_id') != race:
        raise ValueError('forecast output race_id mismatch')
    if value.get('runners') != sum(row.get('status') not in {'SCRATCHED', 'EXCLUDED'} for row in card['runners']):
        raise ValueError('forecast output runner count mismatch')
    identities = [row.get('execution_id') for row in forecasts if isinstance(row, dict)]
    if len(identities) != len(forecasts) or any(not isinstance(key, str) or not key.strip() for key in identities):
        raise ValueError('forecast output missing execution_id')
    if len(set(identities)) != len(identities):
        raise ValueError('forecast output duplicate execution_id')
    roster_path = Path(__file__).resolve().parents[1] / 'data' / 'operations' / 'forecast_roster.json'
    roster = read_json(roster_path)['forecasters']
    if len(forecasts) != len(roster):
        raise ValueError(f'forecast output incomplete forecaster roster: {len(forecasts)}/{len(roster)}')
    names = [row.get('name') for row in forecasts]
    expected_names = {row['name'] for row in roster}
    if len(set(names)) != len(names) or set(names) != expected_names:
        raise ValueError('forecast output forecaster roster names mismatch')
    saved = datetime.fromisoformat(value['saved_at'].replace('Z', '+00:00'))
    off = datetime.fromisoformat(card['off_at'].replace('Z', '+00:00'))
    if saved.tzinfo is None or off.tzinfo is None or saved >= off:
        raise ValueError('forecast output not saved before scheduled start')
    if saved > datetime.now(timezone.utc):
        raise ValueError('forecast output saved_at is in the future')
    if value['phase'] != expected_phase:
        raise ValueError('forecast output phase does not match racecard stage')
    if any(not isinstance(row.get('tickets'), list) for row in forecasts):
        raise ValueError('forecast output missing tickets list')


def run(directory, urls, *, model='local'):
    errors, prepared = [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = [(url, pool.submit(prepare, directory, url)) for url in urls]
        for url, future in pending:
            try:
                race, card = future.result()
                prepared.append((datetime.fromisoformat(card['off_at']), race, card))
            except (OSError, ValueError) as error:
                errors.append({'source': url, 'error': str(error)})
    rows = []
    seen = set()
    for _, race, card in sorted(prepared, key=lambda item: item[0]):
        if race in seen:
            continue
        seen.add(race)
        race_dir = directory / race
        early = card.get('entry_stage') == 'DECLARATIONS'
        card_path = race_dir / ('declarations-racecard.json' if early else 'racecard.json')
        stage_model = 'local' if early else model
        try:
            value = run_panel(directory, card_path, stage_model)
            validate_panel_output(value, race, card, 'DECLARATIONS' if early else 'FINAL')
            rows.append({
                'race_id': race, 'race_name': card['race_name'], 'off_at': card['off_at'],
                'phase': value['phase'], 'publication_window': value['publication_window'],
                'runners': value['runners'], 'forecasters': len(value['forecasts']),
                'tickets': sum(len(row['tickets']) for row in value['forecasts']),
                'roundtable': value['roundtable'], 'saved_at': value['saved_at'],
            })
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
            errors.append({'race_id': race, 'error': str(error)})
    return {'generated_at': datetime.now(timezone.utc).isoformat(), 'requested_urls': len(urls),
            'finalized': sum(row['phase'] == 'FINAL' for row in rows),
            'declarations': sum(row['phase'] == 'DECLARATIONS' for row in rows), 'races': rows, 'errors': errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--url', action='append', required=True)
    parser.add_argument('--model', choices=['local', 'openai'], default='local')
    args = parser.parse_args()
    report = run(args.out, list(dict.fromkeys(args.url)), model=args.model)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(report['errors']))


if __name__ == '__main__':
    sys.exit(main())
