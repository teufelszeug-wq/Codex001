import tempfile
import unittest
from prism_engine.official_racecard_fetch import capture_official_candidate

class Response:
    def __init__(self, url, data=b'official candidate'):
        self.url, self.data = url, data
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def geturl(self): return self.url
    def read(self, n): return self.data[:n]

class Tests(unittest.TestCase):
    def test_capture_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            url='https://www.jra.go.jp/'
            opener=lambda req,timeout: Response(url)
            result=capture_official_candidate(url,d,opener=opener)
            self.assertFalse(result['source_authenticity_verified'])
            with self.assertRaises(FileExistsError): capture_official_candidate(url,d,opener=opener)
    def test_unapproved_host(self):
        with self.assertRaises(ValueError): capture_official_candidate('https://jra.go.jp.evil.com/', '/tmp/never')
    def test_redirect(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): capture_official_candidate('https://www.jra.go.jp/',d,opener=lambda req,timeout: Response('https://evil.example/'))
    def test_oversize(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): capture_official_candidate('https://www.jra.go.jp/',d,opener=lambda req,timeout: Response('https://www.jra.go.jp/',b'abcdef'),max_bytes=3)
