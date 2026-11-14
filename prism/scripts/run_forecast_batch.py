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


def target(url):
    host = urlsplit(url).hostname
    if host in {'jra.go.jp', 'www.jra.go.jp'}:
        date, _, venue, _, _, race = jra_identity(url)
        return f'{date}-JRA-{venue}-{race:02d}', lambda: fetch_jra(url, allow_unframed=True)
    if host == 'www.keiba.go.jp':
        date, venue, race = nar_identity(url)
        return f'{date.replace("-", "")}-NAR-{VENUES[venue][1]}-{race:02d}', lambda: fetch_nar(url)
    raise ValueError('official JRA or NAR racecard URL required')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save_input(path, card):
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            json.dump(card, out, ensure_ascii=False)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        if temporary is not None:
            temporary.unlink()
    return read_json(path)


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
        arguments = ['node', str(PANEL), '--card', str(card_path), '--out', str(directory), '--model', stage_model]
        try:
            result = subprocess.run(arguments, capture_output=True, text=True,
                                    timeout=600, check=False)
            if result.returncode != 0:
                errors.append({'race_id': race, 'error': result.stderr.strip() or 'forecast command failed'})
                continue
            value = json.loads(result.stdout)
            rows.append({
                'race_id': race, 'race_name': card['race_name'], 'off_at': card['off_at'],
                'phase': value['phase'], 'publication_window': value['publication_window'],
                'runners': value['runners'], 'forecasters': len(value['forecasts']),
                'tickets': sum(len(row['tickets']) for row in value['forecasts']),
                'roundtable': value['roundtable'], 'saved_at': value['saved_at'],
            })
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
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
