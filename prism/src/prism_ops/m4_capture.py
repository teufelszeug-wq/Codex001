"""M4 forward evidence capture and independent manifest verification.

The *capture* step never returns VERIFIED_PRE. A trusted service must supply
official observations, S3 clients and a vetted external TSA policy; the saved
candidate must then be independently re-read and re-verified.

This module is a reusable component, not a deployed scheduler/official feed.
"""
import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

from prism_ops.forecast_completion_gate import timestamp, validate_forecast
from prism_ops.pre_provenance_verifier import verify_rfc3161_receipt
from prism_ops.tsa_request import build_request, request_timestamp
from prism_ops.trusted_s3_readback import verified_s3_readback
from prism_ops.worm_storage import store_and_verify


def _canonical_json(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _check_official(forecast, official, *, now):
    """Preflight is an additional barrier; trust comes from the caller service."""
    if not isinstance(official, dict):
        raise ValueError("TRUSTED_OFFICIAL_CONTEXT_REQUIRED")
    if forecast["race_id"] != official.get("official_race_id"):
        raise ValueError("OFFICIAL_RACE_ID_MISMATCH")
    if timestamp(forecast["scheduled_off"]) != timestamp(official["official_scheduled_off"]):
        raise ValueError("OFFICIAL_SCHEDULED_OFF_MISMATCH")
    if (official.get("official_result_exposed") is not False or
            official.get("official_race_cancelled") is not False):
        raise ValueError("OFFICIAL_RACE_NOT_PRE")
    if (not isinstance(official.get("official_entries"), list) or
            not official["official_entries"]):
        raise ValueError("OFFICIAL_ENTRIES_UNAVAILABLE")
    try:
        entries = sorted((x["horse_no"], x["horse_name"])
                         for x in forecast["entries"])
        observed_entries = sorted((x["horse_no"], x["horse_name"])
                                  for x in official["official_entries"])
    except (TypeError, ValueError, KeyError):
        raise ValueError("OFFICIAL_ENTRIES_UNAVAILABLE")
    if entries != observed_entries:
        raise ValueError("OFFICIAL_ENTRIES_MISMATCH")
    observed_at = timestamp(official["official_as_of"])
    saved_at = timestamp(forecast["saved_at"])
    if (observed_at > saved_at or observed_at >= timestamp(forecast["scheduled_off"]) or
            saved_at - observed_at > timedelta(minutes=15) or observed_at > now):
        raise ValueError("OFFICIAL_FEED_STALE_OR_FUTURE")


def capture_pre_candidate(forecast, official_context, *, s3_writer, s3_reader,
                          s3_bucket, s3_prefix, tsa_url, tsa_ca_pem,
                          tsa_policy_oid, tsa_crl_pem, retention_days=30, clock=None):
    """Capture unsigned forecast bytes, third-party TSR and durable proof manifest.

    This method requires independently sourced official_context and trust anchor
    owned by the runner. Its result remains a CANDIDATE until a different
    execution re-reads manifest and object versions.
    """
    if not isinstance(forecast, dict):
        raise ValueError("INVALID_FORECAST")
    now = clock() if clock is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("CLOCK_UNTRUSTED")
    off = timestamp(forecast["scheduled_off"])
    saved = timestamp(forecast["saved_at"])
    if now >= off - timedelta(seconds=30):
        raise ValueError("NO_SAFE_PRE_WINDOW")
    if saved > now or now - saved > timedelta(minutes=3):
        raise ValueError("FORECAST_SAVE_TIME_NOT_CURRENT")
    if (type(retention_days) is not int or retention_days < 1 or
            now + timedelta(days=retention_days) <
            off + timedelta(days=1, minutes=2)):
        raise ValueError("WORM_RETENTION_WINDOW_TOO_SHORT")
    if not isinstance(s3_prefix, str) or not s3_prefix.endswith("/") or not s3_prefix:
        raise ValueError("UNTRUSTED_OBJECT_KEY")
    if not isinstance(tsa_policy_oid, str) or not tsa_policy_oid:
        raise ValueError("TSA_POLICY_UNCONFIGURED")
    if not isinstance(tsa_crl_pem, bytes) or b"-----BEGIN X509 CRL-----" not in tsa_crl_pem:
        raise ValueError("TRUSTED_TSA_CRL_INVALID")
    _check_official(forecast, official_context, now=now)
    shape = validate_forecast(forecast)
    expected = {"CRYPTOGRAPHIC_PROOF_BUNDLE_MISSING",
                "PRE_PROVENANCE_NOT_INDEPENDENTLY_VERIFIED"}
    invalid = [error for error in shape["errors"] if error not in expected]
    if invalid:
        raise ValueError("FORECAST_NOT_READY:" + repr(invalid))

    raw = _canonical_json(forecast)
    fingerprint = _sha256(raw)
    forecast_key = s3_prefix + "forecasts/" + fingerprint + ".json"
    forecast_obj = store_and_verify(
        s3_writer, s3_bucket, forecast_key, raw,
        retention_days=retention_days)
    req_der = build_request(raw)
    resp_der = request_timestamp(tsa_url, req_der)
    reloaded = verified_s3_readback(
        s3_reader, bucket=s3_bucket, key=forecast_key,
        version_id=forecast_obj["version_id"], expected_sha256=fingerprint,
        min_retention_until=off + timedelta(days=1))
    receipt = verify_rfc3161_receipt(
        raw, reloaded["readback_bytes"], resp_der, tsa_ca_pem,
        reloaded["immutable_location"], request_der=req_der,
        required_policy_oid=tsa_policy_oid, trusted_crl_pem=tsa_crl_pem)
    proof_bundle = {"forecast_bytes": raw, "key": forecast_key,
                    "version_id": forecast_obj["version_id"],
                    "tsa_request_der": req_der, "tsa_response_der": resp_der}
    verifier_ctx = dict(official_context,
                        s3_client=s3_reader, bucket=s3_bucket,
                        key_prefix=s3_prefix, tsa_ca_pem=tsa_ca_pem,
                        tsa_policy_oid=tsa_policy_oid,
                        tsa_crl_pem=tsa_crl_pem)
    accepted = validate_forecast(
        forecast, receipt, proof_bundle, verifier_context=verifier_ctx)
    if not accepted["complete"]:
        raise ValueError("M4_PRE_ACCEPTANCE_FAILED:" + repr(accepted["errors"]))

    # Store the ORIGINAL DER request and signed response (not just the receipt).
    # Object Lock protects a specific S3 version. The key is content-addressed.
    manifest = {
        "schema": "PRISM_M4_CANDIDATE_V1",
        "race_id": forecast["race_id"],
        "forecast_sha256": fingerprint,
        "forecast_key": forecast_key,
        "forecast_version_id": forecast_obj["version_id"],
        "tsa_request_der_b64": base64.b64encode(req_der).decode("ascii"),
        "tsa_response_der_b64": base64.b64encode(resp_der).decode("ascii"),
        "tsa_ca_sha256": _sha256(tsa_ca_pem),
        "tsa_crl_sha256": _sha256(tsa_crl_pem),
        "tsa_issuer_crl_pem_b64": base64.b64encode(tsa_crl_pem).decode("ascii"),
        "tsa_policy_oid": tsa_policy_oid,
        "receipt": receipt,
        "official_observation_at": official_context["official_as_of"],
    }
    manifest_raw = _canonical_json(manifest)
    manifest_sha = _sha256(manifest_raw)
    manifest_key = s3_prefix + "proofs/" + manifest_sha + ".json"
    manifest_obj = store_and_verify(
        s3_writer, s3_bucket, manifest_key, manifest_raw,
        retention_days=retention_days)
    verified_s3_readback(
        s3_reader, bucket=s3_bucket, key=manifest_key,
        version_id=manifest_obj["version_id"],
        expected_sha256=manifest_sha,
        min_retention_until=off + timedelta(days=1))
    return {
        "status": "CAPTURED_PRE_CANDIDATE_NOT_INDEPENDENTLY_VERIFIED",
        "race_id": forecast["race_id"],
        "forecast_sha256": fingerprint,
        "forecast_key": forecast_key,
        "forecast_version_id": forecast_obj["version_id"],
        "manifest_sha256": manifest_sha,
        "manifest_key": manifest_key,
        "manifest_version_id": manifest_obj["version_id"],
    }


def verify_candidate_independently(*, s3_reader, s3_bucket, s3_prefix,
                                   manifest_key, manifest_version_id,
                                   manifest_sha256, official_context,
                                   tsa_ca_pem, tsa_crl_pem, tsa_policy_oid):
    """Re-read both immutable objects in a separate trusted process/run.

    Returns a cryptographic acceptance result. Production requires the official
    source adapter, separate credentials and provider-level evidence as well.
    """
    off = timestamp(official_context["official_scheduled_off"])
    if (not isinstance(s3_prefix, str) or not s3_prefix.endswith("/") or
            not isinstance(manifest_key, str) or
            not manifest_key.startswith(s3_prefix + "proofs/")):
        raise ValueError("UNTRUSTED_MANIFEST_KEY")
    stored = verified_s3_readback(
        s3_reader, bucket=s3_bucket, key=manifest_key,
        version_id=manifest_version_id, expected_sha256=manifest_sha256,
        min_retention_until=off + timedelta(days=1))
    raw = stored["readback_bytes"]
    manifest = json.loads(raw)
    if _canonical_json(manifest) != raw or manifest.get("schema") != "PRISM_M4_CANDIDATE_V1":
        raise ValueError("INVALID_MANIFEST")
    if (manifest.get("tsa_policy_oid") != tsa_policy_oid or
            manifest.get("tsa_ca_sha256") != _sha256(tsa_ca_pem) or
            manifest.get("tsa_crl_sha256") != _sha256(tsa_crl_pem)):
        raise ValueError("TSA_TRUST_POLICY_MISMATCH")
    if (manifest.get("race_id") != official_context.get("official_race_id") or
            manifest.get("official_observation_at") != official_context.get("official_as_of")):
        raise ValueError("OFFICIAL_OBSERVATION_MISMATCH")
    # Freeze the exact issuer CRL used at issuance so its historical validation
    # remains replayable if the online issuer publishes a newer CRL.
    preserved_crl = base64.b64decode(
        manifest["tsa_issuer_crl_pem_b64"], validate=True)
    if _sha256(preserved_crl) != manifest["tsa_crl_sha256"]:
        raise ValueError("IMMUTABLE_CRL_MISMATCH")
    # Also require the currently approved CRL to be supplied independently;
    # a producer-stored CRL alone must never become a trusted root.
    if preserved_crl != tsa_crl_pem:
        raise ValueError("TRUSTED_ISSUER_CRL_MISMATCH")
    forecast_key = manifest["forecast_key"]
    if not forecast_key.startswith(s3_prefix + "forecasts/"):
        raise ValueError("UNTRUSTED_FORECAST_KEY")
    forecast_record = verified_s3_readback(
        s3_reader, bucket=s3_bucket, key=forecast_key,
        version_id=manifest["forecast_version_id"],
        expected_sha256=manifest["forecast_sha256"],
        min_retention_until=off + timedelta(days=1))
    forecast_bytes = forecast_record["readback_bytes"]
    forecast = json.loads(forecast_bytes)
    proof_bundle = {
        "forecast_bytes": forecast_bytes,
        "key": forecast_key,
        "version_id": manifest["forecast_version_id"],
        "tsa_request_der": base64.b64decode(manifest["tsa_request_der_b64"], validate=True),
        "tsa_response_der": base64.b64decode(manifest["tsa_response_der_b64"], validate=True),
    }
    ctx = dict(official_context, s3_client=s3_reader, bucket=s3_bucket,
               key_prefix=s3_prefix, tsa_ca_pem=tsa_ca_pem,
               tsa_crl_pem=tsa_crl_pem, tsa_policy_oid=tsa_policy_oid)
    result = validate_forecast(
        forecast, manifest["receipt"], proof_bundle, verifier_context=ctx)
    if not result["complete"]:
        raise ValueError("M4_CANDIDATE_VERIFICATION_FAILED:" + repr(result["errors"]))
    return {
        "status": "CRYPTO_WORM_PRE_VERIFIED_OFFICIAL_SOURCE_STILL_REQUIRED",
        "race_id": result["race_id"],
        "forecast_sha256": result["sha256"],
        "manifest_sha256": manifest_sha256,
        "receipt": manifest["receipt"],
    }
