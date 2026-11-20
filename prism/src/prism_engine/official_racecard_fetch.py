"""Conservative official-source capture; never certifies authenticity automatically."""
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import hashlib
import json

ALLOWED_HOSTS = frozenset({'jra.go.jp', 'www.jra.go.jp', 'keiba.go.jp', 'www.keiba.go.jp'})

def capture_official_candidate(url, directory, *, opener=urlopen, max_bytes=2_000_000):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('unapproved official source URL')
    if max_bytes < 1:
        raise ValueError('invalid size limit')
    request = Request(url, headers={'User-Agent': 'PRISM-Racecard-Archive/1.0'})
    with opener(request, timeout=20) as response:
        final_url = response.geturl()
        final = urlsplit(final_url)
        if final.scheme != 'https' or final.hostname not in ALLOWED_HOSTS:
            raise ValueError('redirect to unapproved host')
        data = response.read(max_bytes + 1)
    if not data or len(data) > max_bytes:
        raise ValueError('empty or oversized response')
    digest = hashlib.sha256(data).hexdigest()
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    target = root / (digest + '.source')
    with target.open('xb') as f:
        f.write(data)
    metadata = {'schema': 'prism.source.capture/v1', 'source_url': url, 'final_url': final_url, 'sha256': digest, 'source_authenticity_verified': False, 'racecard_normalized': False}
    with (root / (digest + '.metadata.json')).open('x', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return metadata
