"""Mocked HTTP boundary tests for the narrow read-only JRA navigation POST."""
from email.message import Message
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.request import Request

from prism_ops.official import OfficialSourceError, _OfficialRedirect, fetch_official_snapshot

INDEX = 'https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dli00%2FF3'
MENU_CODE = 'pw01drl00052026050420261115/BD'
MENU = 'https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01drl00052026050420261115%2FBD'


class JraNavigationFormTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.requests = []

    def opener(self):
        requests = self.requests
        class Response:
            status = 200
            headers = Message()
            headers['Content-Type'] = 'text/html; charset=utf-8'
            def __init__(self, url): self.url = url
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def geturl(self): return self.url
            def read(self, n): return b'<html>synthetic form response</html>'[:n]
        class Opener:
            def open(self, request, **kwargs):
                requests.append(request)
                return Response(request.full_url)
        return Opener()

    def source(self, code=MENU_CODE):
        raw = f'<a href="#" onclick="return doAction(\'/JRADB/accessD.html\', \'{code}\');">menu</a>'.encode()
        path = self.directory / 'observed.html'; path.write_bytes(raw)
        return {'authority':'JRA','official_url':INDEX,'body_path':str(path),
                'source_sha256':sha256(raw).hexdigest(),'captured_at':'2026-11-15T01:00:00Z',
                'encoding':'utf-8','mode':'SYNTHETIC'}

    def test_known_index_posts_lowercase_cname_and_retains_identity_and_raw_bytes(self):
        with patch('prism_ops.official.build_opener', return_value=self.opener()):
            snapshot = fetch_official_snapshot(INDEX, self.directory, form_cname='pw01dli00/F3')
        request = self.requests[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.full_url, 'https://www.jra.go.jp/JRADB/accessD.html')
        self.assertEqual(request.data, b'cname=pw01dli00%2FF3')
        self.assertEqual(snapshot['official_url'], INDEX)
        self.assertEqual(snapshot['requested_url'], INDEX)
        self.assertEqual(snapshot['http_method'], 'POST')
        self.assertEqual(snapshot['posted_cname'], 'pw01dli00/F3')
        self.assertEqual(snapshot['response_url'], request.full_url)
        self.assertEqual(sha256(Path(snapshot['body_path']).read_bytes()).hexdigest(), snapshot['source_sha256'])

    def test_menu_requires_exact_retained_do_action_and_records_its_hash(self):
        source = self.source()
        with patch('prism_ops.official.build_opener', return_value=self.opener()):
            snapshot = fetch_official_snapshot(MENU, self.directory, form_cname=MENU_CODE, navigation_snapshot=source)
        self.assertEqual(snapshot['navigation_source_sha256'], source['source_sha256'])
        self.assertEqual(self.requests[0].data, b'cname=pw01drl00052026050420261115%2FBD')
        Path(source['body_path']).write_text('tampered navigation')
        with self.assertRaises(OfficialSourceError):
            fetch_official_snapshot(MENU, self.directory, form_cname=MENU_CODE, navigation_snapshot=source)

    def test_arbitrary_post_or_unobserved_menu_is_rejected_before_network(self):
        for url, code, source in [
            (INDEX.replace('jra.go.jp', 'keiba.go.jp'), 'pw01dli00/F3', None),
            (INDEX, 'pw01sli00/AF', None),
            (INDEX.replace('accessD', 'arbitrary'), 'pw01dli00/F3', None),
            (MENU, MENU_CODE, None),
            (MENU, MENU_CODE, self.source('pw01drl00052026050420261115/AB')),
            ('https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0108202605041120261115/4C',
             'pw01dde0108202605041120261115/4C', None),
        ]:
            with self.subTest(url=url), patch('prism_ops.official.build_opener') as opened:
                with self.assertRaises(OfficialSourceError):
                    fetch_official_snapshot(url, self.directory, form_cname=code, navigation_snapshot=source)
                opened.assert_not_called()

    def test_https_downgrade_remains_forbidden(self):
        with self.assertRaises(OfficialSourceError):
            _OfficialRedirect().redirect_request(Request(INDEX, data=b'cname=x'), None, 301, '', {},
                                                 'http://www.jra.go.jp/error/error013.html')


if __name__ == '__main__':
    unittest.main()
