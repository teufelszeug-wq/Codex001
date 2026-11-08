#!/usr/bin/env python3
"""PRISM M4 live-provider transport CLI (NOT an official-source certification).

Requires boto3, externally provisioned AWS role, preconfigured Object Lock
COMPLIANCE bucket, vetted TSA URL and TSA CA/policy. No credentials on argv.

Run 'capture' before off, and 'verify' in a different process/role. A JSON
official context file alone is not proof of JRA/NAR source authenticity.
"""
import argparse
import json
from pathlib import Path
import sys

from prism_ops.m4_capture import capture_pre_candidate, verify_candidate_independently


def _load_json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return data


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for op in ("capture", "verify"):
        p = sub.add_parser(op)
        p.add_argument("--official-context", required=True,
                       help="verified official-feed adapter output (trusted service only)")
        p.add_argument("--bucket", required=True)
        p.add_argument("--prefix", required=True)
        p.add_argument("--region")
        p.add_argument("--tsa-ca-pem", required=True)
        p.add_argument("--tsa-crl-pem", required=True)
        p.add_argument("--tsa-policy-oid", required=True)
        if op == "capture":
            p.add_argument("--forecast", required=True)
            p.add_argument("--tsa-url", required=True)
            p.add_argument("--retention-days", type=int, default=30)
        else:
            p.add_argument("--manifest-pointer", required=True,
                           help="persisted capture result with pinned version IDs and SHA256")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        import boto3
    except ImportError as exc:
        raise SystemExit("boto3 is required for real AWS S3 transport") from exc

    # Two clients for component boundary. Run verification separately under
    # an independent read-only IAM role for genuine independent evidence.
    session = boto3.session.Session(region_name=args.region)
    writer = session.client("s3")
    reader = session.client("s3")
    official = _load_json(args.official_context)
    ca = Path(args.tsa_ca_pem).read_bytes()
    crl = Path(args.tsa_crl_pem).read_bytes()
    if args.operation == "capture":
        forecast = _load_json(args.forecast)
        result = capture_pre_candidate(
            forecast, official,
            s3_writer=writer, s3_reader=reader,
            s3_bucket=args.bucket, s3_prefix=args.prefix,
            tsa_url=args.tsa_url, tsa_ca_pem=ca,
            tsa_policy_oid=args.tsa_policy_oid,
            tsa_crl_pem=crl,
            retention_days=args.retention_days)
    else:
        pointer = _load_json(args.manifest_pointer)
        if pointer.get("status") != "CAPTURED_PRE_CANDIDATE_NOT_INDEPENDENTLY_VERIFIED":
            raise ValueError("INVALID_CAPTURE_RECORD")
        result = verify_candidate_independently(
            s3_reader=reader, s3_bucket=args.bucket, s3_prefix=args.prefix,
            manifest_key=pointer["manifest_key"],
            manifest_version_id=pointer["manifest_version_id"],
            manifest_sha256=pointer["manifest_sha256"],
            official_context=official, tsa_ca_pem=ca,
            tsa_crl_pem=crl, tsa_policy_oid=args.tsa_policy_oid)
    json.dump(result, sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
