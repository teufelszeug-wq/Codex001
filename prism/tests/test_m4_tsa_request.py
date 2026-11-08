"""M4.2 TSA transport contract tests: no real TSA is contacted."""
import unittest
from unittest.mock import patch
from prism_ops.tsa_request import build_request, request_timestamp

class TSARequestTests(unittest.TestCase):
    def test_empty_forecast_rejected(self):
        with self.assertRaisesRegex(ValueError, "FORECAST_BYTES_REQUIRED"):
            build_request(b"")

    @patch("prism_ops.tsa_request.subprocess.run")
    def test_nonce_request_generation(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = b"DER-QUERY"
        self.assertEqual(build_request(b"forecast"), b"DER-QUERY")
        args = run.call_args.args[0]
        self.assertIn("-sha256", args)
        self.assertNotIn("-no_nonce", args)

    def test_http_url_rejected(self):
        with self.assertRaisesRegex(ValueError, "TSA_HTTPS_URL_REQUIRED"):
            request_timestamp("http://tsa.example.org", b"request")

    def test_missing_request_rejected(self):
        with self.assertRaisesRegex(ValueError, "RFC3161_REQUEST_MISSING"):
            request_timestamp("https://tsa.example.org", b"")

    @patch("prism_ops.tsa_request.urlopen")
    def test_response_content_type_enforced(self, opener):
        response = opener.return_value.__enter__.return_value
        response.status = 200
        response.headers = {"Content-Type": "text/html"}
        with self.assertRaisesRegex(ValueError, "TSA_CONTENT_TYPE_INVALID"):
            request_timestamp("https://tsa.example.org", b"request")

    @patch("prism_ops.tsa_request.urlopen")
    def test_mocked_tsa_reply(self, opener):
        response = opener.return_value.__enter__.return_value
        response.status = 200
        response.headers = {"Content-Type": "application/timestamp-reply"}
        response.read.return_value = b"DER-REPLY"
        self.assertEqual(request_timestamp("https://tsa.example.org", b"request"), b"DER-REPLY")

if __name__ == "__main__":
    unittest.main()
