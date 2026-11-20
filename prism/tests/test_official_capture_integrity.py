"""Regression tests for capture integrity and redirect validation."""
import hashlib
import io
import json
from pathlib import Path
import pytest
from prism_engine.official_racecard_fetch import capture_official_candidate


class Response:
    def __init__(self, url, data=b'official candidate'):
        self.url, self.stream = url, io.BytesIO(data)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.stream.close()
    def geturl(self):
        return self.url
    def read(self, n):
        return self.stream.read(n)


def test_reject_redirect_credentials(tmp_path):
    with pytest.raises(ValueError, match='redirect'):
        capture_official_candidate(
            'https://www.jra.go.jp/', tmp_path,
            opener=lambda *a, **kw: Response('https://user:pass@www.jra.go.jp/'))
    assert not list(tmp_path.iterdir())


def test_reject_redirect_nonstandard_port(tmp_path):
    with pytest.raises(ValueError, match='redirect'):
        capture_official_candidate(
            'https://www.jra.go.jp/', tmp_path,
            opener=lambda *a, **kw: Response('https://www.jra.go.jp:8443/'))


def test_capture_pair_and_no_overwrite(tmp_path):
    data = b'candidate'
    digest = hashlib.sha256(data).hexdigest()
    call = lambda: capture_official_candidate(
        'https://www.jra.go.jp/', tmp_path,
        opener=lambda *a, **kw: Response('https://www.jra.go.jp/', data))
    receipt = call()
    assert receipt['source_authenticity_verified'] is False
    assert (tmp_path / (digest + '.source')).read_bytes() == data
    assert json.loads((tmp_path / (digest + '.metadata.json')).read_text())['sha256'] == digest
    with pytest.raises(FileExistsError):
        call()
