"""Conservative official-source capture; never certifies authenticity automatically."""
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import hashlib
import json

ALLOWED_HOSTS = frozenset({'jra.go.jp', 'www.jra.go.jp', 'keiba.go.jp', 'www.keiba.go.jp'})


def _approved(url):
    try:
        p = urlsplit(url)
        return (p.scheme == 'https' and p.hostname in ALLOWED_HOSTS
                and p.username is None and p.password is None
                and p.port in (None, 443))
    except ValueError:
        return False


def capture_official_candidate(url, directory, *, opener=urlopen, max_bytes=2_000_000):
    if not _approved(url):
        raise ValueError('unapproved official source URL')
    if max_bytes < 1:
        raise ValueError('invalid size limit')
    request = Request(url, headers={'User-Agent': 'PRISM-Racecard-Archive/1.0'})
    with opener(request, timeout=20) as response:
        final_url = response.geturl()
        if not _approved(final_url):
            raise ValueError('redirect to unapproved host')
        data = response.read(max_bytes + 1)
    if not data or len(data) > max_bytes:
        raise ValueError('empty or oversized response')
    digest = hashlib.sha256(data).hexdigest()
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    target = root / (digest + '.source')
    metadata_path = root / (digest + '.metadata.json')
    # Reject an existing pair before touching either artifact.
    if target.exists() or metadata_path.exists():
        raise FileExistsError('capture already exists or is incomplete')
    metadata = {'schema': 'prism.source.capture/v1', 'source_url': url,
                'final_url': final_url, 'sha256': digest,
                'source_authenticity_verified': False, 'racecard_normalized': False}
    try:
        with target.open('xb') as f:
            f.write(data)
        with metadata_path.open('x', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
    except Exception:
        # Never leave a new orphan source after metadata-write failure.
        # Pre-existing files are protected by the initial existence check.
        if target.exists() and not metadata_path.exists():
            target.unlink()
        raise
    return metadata
