# PRISM M4 — Live RFC3161 TSA + AWS Object Lock runbook

**2026-11-08 status: NOT DEPLOYED / M4 NOT COMPLETE.**
Synthetic local-CA OpenSSL and mocked S3 E2E tests are NOT third-party timestamps or AWS provider evidence. They must never be counted as genuinely certified PRE.

## Source of implementation
- Capture and independent verification: prism/src/prism_ops/m4_capture.py
- Live-provider process CLI: prism/scripts/m4_capture_cli.py
- RFC3161 request/response: prism/src/prism_ops/tsa_request.py
- Signed-policy and chain validation: prism/src/prism_ops/pre_provenance_verifier.py
- WORM persistence: prism/src/prism_ops/worm_storage.py
- Independent version readback: prism/src/prism_ops/trusted_s3_readback.py
- Forecast/full-agent 100-yen acceptance: prism/src/prism_ops/forecast_completion_gate.py
- Official settlement boundary: prism/src/prism_ops/verified_settlement.py
- Regression CI: .github/workflows/prism-m4-contract.yml

## P0 prerequisites that cannot be inferred from a green CI
1. Vetted third-party TSA URL (HTTPS POST for timestamp-query), independently trusted CA and mandatory signed policy OID. Confirm signer chain, EKU, revocation and genTime before *actual* official off time. **Mandatory live CRL/OCSP revocation verification is not yet implemented: release BLOCKED.**
2. Private versioned AWS S3 bucket with Object Lock COMPLIANCE; configured retention, billing budget and approved write IAM role. A separate read-only IAM role must fetch the pinned VersionId and provider retention. AWS Object Lock applies to a *specific version*; new versions with the same key are still possible.
3. Trusted official JRA/NAR provider adapter that records source evidence, race_id, actual off-time mutations, entries, scratches, cancellation and result embargo. A manually supplied JSON file is NOT independent official authenticity.
4. Durable before-off scheduler, all required named specialist AI choices, horse names and 100-yen tickets or explicit passes, retries and alerts; race must not have begun.
5. Separate-process proof readback followed by independently sourced official payout/return/late-result checks and a reproducible settlement audit. Never turn unknown outcomes into losses.

AWS: https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html

OpenSSL: https://docs.openssl.org/master/man1/openssl-ts/

## Live capture command (authorized external services only)

Do not store cloud secrets, restricted official raw bytes, full forecast data or the DER evidence in this public GitHub repository. Configure AWS IAM roles via environment/profile.

~~~
python -m pip install boto3
export PYTHONPATH=prism/src
export AWS_PROFILE=prism-m4-writer
python prism/scripts/m4_capture_cli.py capture \
  --forecast /secure/forecast.json \
  --official-context /trusted/official-observation.json \
  --bucket YOUR-OBJECT-LOCK-BUCKET --prefix pre/ \
  --region ap-northeast-1 \
  --tsa-url https://YOUR-APPROVED-TSA \
  --tsa-ca-pem /secure/approved-tsa-ca.pem \
  --tsa-policy-oid YOUR-SIGNED-POLICY-OID \
  --retention-days 30 > /secure/candidate-pointer.json
~~~

Expected status: CAPTURED_PRE_CANDIDATE_NOT_INDEPENDENTLY_VERIFIED.
The forecast and original TSQ/TSR manifest are persisted as *separate*, pinned S3 COMPLIANCE versions.

## Independent verification command (new process and read-only role)

~~~
export PYTHONPATH=prism/src
export AWS_PROFILE=prism-m4-readonly
python prism/scripts/m4_capture_cli.py verify \
  --manifest-pointer /secure/candidate-pointer.json \
  --official-context /trusted/official-observation.json \
  --bucket YOUR-OBJECT-LOCK-BUCKET --prefix pre/ \
  --region ap-northeast-1 \
  --tsa-ca-pem /secure/approved-tsa-ca.pem \
  --tsa-policy-oid YOUR-SIGNED-POLICY-OID \
  > /secure/independent-verification.json
~~~

Expected component status:
CRYPTO_WORM_PRE_VERIFIED_OFFICIAL_SOURCE_STILL_REQUIRED.
Even this result is not a live M4 completion until trusted provider official
observation, mandatory CRL/OCSP, audit independence and off-time evidence are verified.

## Acceptance record for the genuine first future race

- Official race ID/URL, runner list, time-change ledger, source_as_of and actual off.
- Canonical locked forecast SHA256, all specialist outputs, 100-yen tickets/passes.
- Original TSQ and signed TSR bytes/hash/nonce, signed genTime/policy, pinned CA.
- TSA signer chain/EKU/revocation evidence; before-off timestamp comparison.
- S3 COMPLIANCE retention, bucket/key/VersionId and SHA256 readback in a second role.
- Original DER evidence manifest bucket/key/VersionId/SHA256 and immutable audit.
- Genuine post-race official payout and return data, paper and per-agent settlement.
- GitHub commit SHA and Actions run ID, but mock CI cannot replace external evidence.

M4 is BLOCKED until all of the above have been independently verified for
at least one real future race, without backdating.
