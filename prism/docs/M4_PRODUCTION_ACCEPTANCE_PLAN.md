# M4 PRE Snapshot production acceptance (2026-11-08)

## Current evidence
- RFC3161/OpenSSL verification and canonical-byte/readback checks: implemented, **not proven in production**.
- Unit test cases: committed, **execution and results unverified**.
- Trusted TSA request client, real certificate-chain/policy verification, certificate revocation handling, nonce/replay policy, trusted clock: **not implemented**.
- Immutable storage identity validation: **not implemented**. Prefix checks are not proof that a Git commit exists, is pinned, or is protected from deletion.
- Proof bundle is caller supplied. Bytes must be independently retrieved by the trusted verifier from the exact pinned storage object, not accepted from an untrusted caller.
- External issuance and pre-off timestamp: **0 confirmed**. Golden/Forward PRE: **0 confirmed**.

## P0 - Required to declare M4 complete
1. Canonical serialization specification, input snapshot, required specialist roster, complete picks and tickets, sources, as-of times, and result exposure checks.
2. Upload forecast bytes before off to an immutable versioned location (e.g. S3 Object Lock compliance mode with version ID and retention, or equivalent audited WORM). Verify storage version and retention via provider API; GitHub path/commit string alone is insufficient.
3. Independently retrieve the exact bytes from the pinned object version and verify SHA-256.
4. Generate RFC3161 request containing SHA-256 imprint and nonce; send to approved TSA; store DER response. Verify TSA signature, trusted certificate chain, EKU/policy, nonce and message imprint, genTime before scheduled_off. Persist trust anchors and proof.
5. Tie the validated timestamp and independently retrieved storage version to the exact same byte sequence. Reject mismatch, result exposure, late receipt, unknown official runner roster, duplicate input version, partial AI output.
6. Run positive and negative tests with real OpenSSL/TSA material; test expired cert, bad signer, revoked signer, wrong hash, after-off, malformed timestamp, storage mutation, readback outage, duplicate job and retry.
7. Run one actual upcoming race end-to-end before post time. Store immutable evidence, independently read back in a new process/run, audit as VERIFIED_PRE, and settle from official payout only after race.
8. Prove M5 settlement rejects all forecasts without full M4 evidence.

## M0-M9 parallel dependencies
M0 canonical ledger and Notion synchronization; M1 official JRA/NAR runner/withdrawal feeds; M2 deterministic prediction; M3 full specialist outputs; **M4 trustworthy snapshot**; M5 official settlement; M6 learning ledger; M7 five-topic authentic discussions; M8 vertical newspaper QA; M9 scheduler, retries, metrics, observability.

## Release gates
- M4 status = BLOCKED until P0 all verified. Do not count source commits or unit-test creation as a completed race.
- Do not backfill PRE after off. Missing official or cryptographic evidence = UNVERIFIED_PRE_FORECAST.
- NO SNAPSHOT = NO BACKTEST.
