"""Fetch a JSON racecard from a constrained official host, then stage unverified.

HTML pages are not converted into invented racecards. This does not authenticate
that JSON found on an official host is an official racecard.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from stage_racecard_cli import stage_file

OFFICIAL_HOSTS = frozenset({'jra.go.jp', 'www.jra.go.jp', 'www.keiba.go.jp', 'keiba.go.jp'})
MAX_BYTES = 2_000_000

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirect rejected; supply canonical official URL')

def fetch_to_stage(url, raw_path, staged_path, race_id, *, opener=None):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in OFFICIAL_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('HTTPS official allowlisted host required')
    raw, staged = Path(raw_path), Path(staged_path)
    if raw.resolve() == staged.resolve():
        raise ValueError('raw and staged paths must differ')
    if raw.exists() or staged.exists():
        raise FileExistsError('refusing to overwrite existing artifact')
    client = opener or build_opener(NoRedirect())
    with client.open(Request(url, headers={'Accept':'application/json','User-Agent':'PRISM-research/1.0'}), timeout=15) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('response exceeds size limit')
        actual = urlparse(response.geturl())
        if actual.scheme != 'https' or actual.hostname not in OFFICIAL_HOSTS:
            raise ValueError('response URL is not an official host')
    from official_racecard_ingest import stage_official_racecard
    timestamp = datetime.now(timezone.utc).isoformat()
    stage_official_racecard(body, source_url=url, retrieved_at=timestamp, expected_race_id=race_id)
    raw.parent.mkdir(parents=True, exist_ok=True)
    with raw.open('xb') as stream:
        stream.write(body)
    return stage_file(raw, staged, source_url=url, retrieved_at=timestamp, race_id=race_id)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('url', 'raw', 'staged', 'race-id'):
        parser.add_argument('--'+key, required=True)
    a = parser.parse_args()
    result = fetch_to_stage(a.url, a.raw, a.staged, a.race_id)
    print(json.dumps({'race_id':result['race_id'],'status':result['provenance_status'],'sha256':result['source_sha256']}))

if __name__ == '__main__':
    main()
