"""RFC3161 request generation and HTTP transport (issuance is not verification).

Uses OpenSSL for a SHA-256 request with a random nonce. A response must be
verified separately against a pinned trust policy and the original request.
"""
import subprocess
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse

def build_request(forecast_bytes, *, openssl="openssl"):
    if not isinstance(forecast_bytes, bytes) or not forecast_bytes:
        raise ValueError("FORECAST_BYTES_REQUIRED")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "forecast.bin"
        path.write_bytes(forecast_bytes)
        result = subprocess.run([openssl, "ts", "-query", "-data", str(path),
                                 "-sha256", "-cert"],
                                capture_output=True, timeout=20)
        if result.returncode or not result.stdout:
            raise ValueError("RFC3161_REQUEST_GENERATION_FAILED")
        return result.stdout

def request_timestamp(tsa_url, request_der, *, timeout=10):
    parsed = urlparse(tsa_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("TSA_HTTPS_URL_REQUIRED")
    if not isinstance(request_der, bytes) or not request_der:
        raise ValueError("RFC3161_REQUEST_MISSING")
    req = Request(tsa_url, data=request_der, method="POST",
                  headers={"Content-Type": "application/timestamp-query",
                           "Accept": "application/timestamp-reply"})
    with urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("TSA_HTTP_ERROR")
        if "application/timestamp-reply" not in response.headers.get("Content-Type", "").lower():
            raise ValueError("TSA_CONTENT_TYPE_INVALID")
        der = response.read(1024 * 1024 + 1)
    if not der or len(der) > 1024 * 1024:
        raise ValueError("TSA_RESPONSE_SIZE_INVALID")
    return der
