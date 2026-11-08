"""M4 trusted S3 version readback: independently retrieve and inspect Object Lock.

Never treat a caller-supplied immutable_location or readback_bytes as proof.
Requires a separately configured S3 client with permissions to read the object
and its retention. This function does not establish RFC3161 authenticity.
"""
import hashlib
from datetime import datetime, timezone

def verified_s3_readback(s3, *, bucket, key, version_id, expected_sha256,
                         min_retention_until, max_bytes=16 * 1024 * 1024):
    if not all(isinstance(v, str) and v for v in
               (bucket, key, version_id, expected_sha256)):
        raise ValueError("PINNED_OBJECT_IDENTITY_REQUIRED")
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("INVALID_READBACK_SIZE_LIMIT")
    if version_id == "null":
        raise ValueError("VERSION_ID_MISSING")
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("INVALID_SHA256")
    if not isinstance(min_retention_until, datetime) or min_retention_until.tzinfo is None:
        raise ValueError("RETENTION_DEADLINE_REQUIRED")
    retention = s3.get_object_retention(Bucket=bucket, Key=key,
                                        VersionId=version_id)["Retention"]
    until = retention.get("RetainUntilDate")
    if (retention.get("Mode") != "COMPLIANCE" or
            not isinstance(until, datetime) or until.tzinfo is None or
            until.astimezone(timezone.utc) < min_retention_until.astimezone(timezone.utc)):
        raise ValueError("WORM_RETENTION_UNVERIFIED")
    obj = s3.get_object(Bucket=bucket, Key=key, VersionId=version_id)
    if obj.get("VersionId") != version_id:
        raise ValueError("VERSION_READBACK_MISMATCH")
    # Never download an unbounded object into the trusted verifier process.
    raw = obj["Body"].read(max_bytes + 1)
    if not isinstance(raw, bytes) or len(raw) > max_bytes:
        raise ValueError("READBACK_SIZE_LIMIT_EXCEEDED")
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("PERSISTENCE_READBACK_FAILED")
    return {"forecast_bytes": raw, "readback_bytes": raw,
            "immutable_location": f"s3-version:{bucket}/{key}?versionId={version_id}",
            "readback_sha256": expected_sha256,
            "retention_verified": True,
            "retention_until": until.isoformat()}
