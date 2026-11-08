# PRISM M4 Resolution Submilestones — 2026-11-08

## Hard acceptance rule
M4 is complete ONLY after a genuine future race has a canonical pre-off forecast, an externally signed RFC3161 timestamp, a provider-verified WORM object version, independent readback, and a reproducible VERIFIED_PRE audit. No backdated PRE.

| ID | Deliverable | Acceptance evidence | Status |
|---|---|---|---|
| M4.0 | Reproduce baseline and CI regressions | successful workflow run with SHA and logs | CI PASS (run 42433180520 for prior changes; newest tests pending) |
| M4.1 | Separate forecast from provenance envelope; bind signed bytes to forecast | source and regression committed | IMPLEMENTED, CI PASS for prior SHA; newest tests pending |
| M4.2 | TSA client with nonce, SHA-256 imprint and DER persistence | real issued token, nonce and imprint verified | REQUEST/HTTPS ADAPTER IMPLEMENTED; real issuance BLOCKED |
| M4.3 | Trust policy for TSA certificate chain, EKU, revocation, signer policy | real positive and adversarial crypto tests | BLOCKED |
| M4.4 | Versioned WORM storage provider | object-lock retention and version ID verified from provider | S3 ADAPTER IMPLEMENTED; real provider BLOCKED |
| M4.5 | Independent readback from pinned object version | SHA-256 equality in separate process | SAME-PROCESS ADAPTER IMPLEMENTED; independent-process test BLOCKED |
| M4.6 | Race-off scheduler with deadlines and retries | observed real pre-off success and safe failures | BLOCKED |
| M4.7 | Full agent roster, official entries and results isolation | independently verified PRE payload | BLOCKED (M1/M2/M3 dependencies) |
| M4.8 | E2E acceptance and M5 settlement handoff | 1 genuine VERIFIED_PRE race and subsequent official settlement | BLOCKED |
| M4.9 | Production observability and disaster recovery | persisted audit, alerts, recovery drill | BLOCKED |

## Execution strategy
- Parallel track A (M4.1–M4.3): data contract, TSA request and verification, adversarial tests.
- Parallel track B (M4.4–M4.5): WORM storage, independent object readback, retention verification.
- Parallel track C (M4.6–M4.7): M1 official feed, M2 inference, M3 all-AI picks, race scheduler.
- Integration track (M4.8–M4.9): acceptance and M5 settlement only after A/B/C pass.

## External prerequisites
- Approved TSA URL, trust anchor, policy OID and access credentials if required.
- WORM provider account, bucket/region, object-lock compliance retention policy and least-privilege credentials.
- Always-on execution runner with permission to use those services.
- No credentials in GitHub code or PRISM artifacts. Use secret storage.
- Official JRA/NAR runner and scheduled-off data, plus all-AI prediction output before off.

## Current metrics
- Newly verified PRE races: 0 (not observed).
- Newly settled official races: 0 (not observed).
- No claim of full M4 completion, live TSA issuance or live WORM storage verification.

## 2026-11-08 implementation continuation
- Added `prism_ops.tsa_request`: OpenSSL RFC3161 SHA-256 request (default nonce), HTTPS POST with timeout/content-type/size limits. Real TSA request/nonce matching remains unverified.
- Added `prism_ops.worm_storage`: S3 Object Lock COMPLIANCE write, version ID, retention query and version-pinned readback. Requires configured client and real cloud provider validation.
- Added TSA and WORM mocked contract tests; CI workflow expanded. Do not treat mocked success as external evidence.
- **Known integration blocker:** provenance verifier still accepts caller-provided readback bytes and location; must fetch object itself using trusted storage configuration and bind RFC3161 response to original nonce request. This is mandatory before VERIFIED_PRE.
