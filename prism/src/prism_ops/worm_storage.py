"""S3 Object Lock compliance-mode persistence and independent version readback.

The caller supplies a configured boto3 S3 client. This adapter never claims a
storage location immutable based on a string or an unverified API response.
"""
import hashlib
from datetime import datetime, timezone, timedelta

def store_and_verify(s3, bucket, key, payload, *, retention_days=30):
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("SNAPSHOT_BYTES_REQUIRED")
    if not bucket or not key or retention_days < 1:
        raise ValueError("INVALID_WORM_CONFIG")
    until = datetime.now(timezone.utc) + timedelta(days=retention_days)
    put = s3.put_object(Bucket=bucket, Key=key, Body=payload,
                        ObjectLockMode="COMPLIANCE", ObjectLockRetainUntilDate=until,
                        ChecksumAlgorithm="SHA256")
    version = put.get("VersionId")
    if not version or version == "null":
        raise ValueError("VERSION_ID_MISSING")
    retention = s3.get_object_retention(Bucket=bucket, Key=key, VersionId=version)["Retention"]
    if retention.get("Mode") != "COMPLIANCE" or retention.get("RetainUntilDate") is None:
        raise ValueError("WORM_RETENTION_NOT_VERIFIED")
    retain_until = retention["RetainUntilDate"]
    if retain_until.tzinfo is None or retain_until.astimezone(timezone.utc) < until - timedelta(seconds=2):
        raise ValueError("WORM_RETENTION_TOO_SHORT")
    read = s3.get_object(Bucket=bucket, Key=key, VersionId=version)
    actual = read["Body"].read()
    if actual != payload:
        raise ValueError("PERSISTENCE_READBACK_FAILED")
    return {"bucket": bucket, "key": key, "version_id": version,
            "sha256": hashlib.sha256(actual).hexdigest(),
            "retain_until": retain_until.isoformat(),
            "immutable_location": "s3-version:" + bucket + "/" + key + "?versionId=" + version}
