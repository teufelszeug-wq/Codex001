"""RFC3161 PRE evidence verification. No network or timestamp issuance.

A receipt is accepted only after the original forecast bytes are fetched again,
the RFC3161 response is checked by OpenSSL against a configured trusted TSA
certificate bundle, and the token's genTime is independently extracted.
The caller must supply a pinned immutable object location and an exact byte
readback; the caller's timestamps/booleans are never authoritative.
"""
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def verify_rfc3161_receipt(forecast_bytes, readback_bytes, tsa_response_der,
                           trusted_tsa_ca_pem, immutable_location,
                           *, request_der=None, required_policy_oid=None,
                           trusted_crl_pem=None, openssl="openssl"):
    if not isinstance(forecast_bytes, bytes) or not isinstance(readback_bytes, bytes):
        raise ValueError("FORECAST_BYTES_REQUIRED")
    if forecast_bytes != readback_bytes:
        raise ValueError("PERSISTENCE_READBACK_FAILED")
    if not isinstance(request_der, bytes) or not request_der:
        raise ValueError("RFC3161_ORIGINAL_REQUEST_REQUIRED")
    if not isinstance(tsa_response_der, bytes) or not tsa_response_der:
        raise ValueError("RFC3161_TOKEN_MISSING")
    if not isinstance(trusted_tsa_ca_pem, bytes) or not trusted_tsa_ca_pem:
        raise ValueError("TRUSTED_TSA_CA_MISSING")
    if not immutable_location or not immutable_location.startswith(("git-commit:", "s3-version:", "object-lock:")):
        raise ValueError("IMMUTABLE_LOCATION_UNVERIFIED")
    forecast = json.loads(forecast_bytes.decode("utf-8"))
    if not isinstance(forecast, dict):
        raise ValueError("INVALID_FORECAST")
    if forecast_bytes != json.dumps(forecast, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"):
        raise ValueError("NONCANONICAL_FORECAST_BYTES")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "forecast.json").write_bytes(forecast_bytes)
        (base / "stamp.tsr").write_bytes(tsa_response_der)
        (base / "request.tsq").write_bytes(request_der)
        if trusted_crl_pem is not None:
            if (not isinstance(trusted_crl_pem, bytes) or
                    b"-----BEGIN X509 CRL-----" not in trusted_crl_pem):
                raise ValueError("TRUSTED_TSA_CRL_INVALID")
            # OpenSSL's trusted CAfile can carry issuer CRLs. -crl_check
            # independently checks the signer's revocation and CRL validity.
            (base / "tsa-ca.pem").write_bytes(
                trusted_tsa_ca_pem + b"\\n" + trusted_crl_pem)
        else:
            (base / "tsa-ca.pem").write_bytes(trusted_tsa_ca_pem)
        query = subprocess.run(
            [openssl, "ts", "-query", "-in", str(base / "request.tsq"), "-text"],
            capture_output=True, text=True, timeout=20)
        if query.returncode:
            raise ValueError("RFC3161_REQUEST_UNREADABLE")
        if not re.search(r"Hash Algorithm:\s*sha256\b", query.stdout, re.I):
            raise ValueError("RFC3161_REQUEST_HASH_NOT_SHA256")
        match_data = re.search(
            r"Message data:\s*\n((?:\s*[0-9a-fA-F]{4}\s*-.*\n)+)",
            query.stdout)
        if not match_data:
            raise ValueError("RFC3161_REQUEST_IMPRINT_UNREADABLE")
        # OpenSSL prints the request imprint as offset-prefixed hex rows.
        rows = match_data.group(1).splitlines()
        imprint = "".join(
            "".join(re.findall(r"[0-9a-fA-F]{2}", re.split(r"\s{2,}", row.split("-", 1)[1].replace("-", " "))[0]))
            for row in rows)
        if len(imprint) != 64 or imprint.lower() != hashlib.sha256(forecast_bytes).hexdigest():
            raise ValueError("RFC3161_REQUEST_IMPRINT_MISMATCH")
        cmd = [openssl, "ts", "-verify", "-queryfile", str(base / "request.tsq"),
               "-in", str(base / "stamp.tsr"), "-CAfile", str(base / "tsa-ca.pem")]
        if trusted_crl_pem is not None:
            cmd.append("-crl_check")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode != 0:
            raise ValueError("RFC3161_SIGNATURE_OR_IMPRINT_INVALID")
        info = subprocess.run([openssl, "ts", "-reply", "-in",
                               str(base / "stamp.tsr"), "-text"],
                              capture_output=True, text=True, timeout=20)
        if info.returncode != 0:
            raise ValueError("RFC3161_TIME_UNREADABLE")
        # The selected TSA policy must be authenticated inside signed TSTInfo,
        # not merely asserted by the requester or the transport endpoint.
        if required_policy_oid is not None:
            if (not isinstance(required_policy_oid, str) or
                    not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", required_policy_oid)):
                raise ValueError("RFC3161_POLICY_UNCONFIGURED")
            policy = re.search(
                r"^\s*Policy OID:\s*([0-9]+(?:\.[0-9]+)+)\s*$",
                info.stdout, re.MULTILINE)
            if not policy or policy.group(1) != required_policy_oid:
                raise ValueError("RFC3161_POLICY_MISMATCH")
        match = re.search(r"^\s*Time stamp:\s*(.+)$", info.stdout, re.MULTILINE)
        if not match:
            raise ValueError("RFC3161_TIME_MISSING")
        raw = match.group(1).strip()
        # OpenSSL prints e.g. "Nov  8 00:30:00 2026 GMT".
        try:
            stamp = datetime.strptime(" ".join(raw.split()), "%b %d %H:%M:%S %Y GMT").replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError("RFC3161_TIME_UNPARSEABLE") from exc
    from prism_ops.forecast_completion_gate import timestamp, digest
    if stamp >= timestamp(forecast["scheduled_off"]):
        raise ValueError("RFC3161_TIMESTAMP_AFTER_OFF")
    if stamp < timestamp(forecast["saved_at"]):
        raise ValueError("RFC3161_TIMESTAMP_BEFORE_FORECAST_SAVE")
    if stamp < timestamp(forecast["source_as_of"]):
        raise ValueError("RFC3161_TIMESTAMP_BEFORE_SOURCE")
    # This receipt describes the bytes actually signed, not a reconstructed dict.
    return {
        "verified_by": "PRISM_TRUSTED_PERSISTENCE_VERIFIER",
        "race_id": forecast["race_id"],
        "forecast_sha256": digest(forecast),
        "raw_forecast_sha256": hashlib.sha256(forecast_bytes).hexdigest(),
        "trusted_saved_at": stamp.isoformat(),
        "immutable_location": immutable_location,
        "readback_verified": True,
        "timestamp_verified": True,
        "signer_revocation_checked": trusted_crl_pem is not None,
        "proof_kind": "RFC3161_OPENSSL_VERIFIED",
    }
