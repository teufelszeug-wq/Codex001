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

## Local-first development track (2026-11-08)
| ID | Work | Status | Acceptance |
|---|---|---|---|
| M4.2a | Canonical local Snapshot Engine | CODE COMMITTED, CI PENDING | exclusive atomic object creation, canonical SHA256 |
| M4.2b | Local audit hash chain | CODE COMMITTED, CI PENDING | tamper and gap rejection; no third-party trust claim |
| M4.4a | Local content-addressed object store | CODE COMMITTED, CI PENDING | duplicate write rejected; object hash verified |
| M4.5a | Independent invocation readback audit | CODE COMMITTED, CI PENDING | all objects and events re-read; no VERIFIED_PRE |
| M4.6a | Single-writer scheduling and locking | NOT DONE | concurrent writers, deadline, retries and crash recovery tested |
| M4.8a | Real future race LOCAL_PRE | NOT DONE | official inputs, complete AI predictions and genuine pre-off run |
| M4.8b | External VERIFIED_PRE | NOT DONE | TSA, pinned trust and provider WORM independently verified |

Local PRE is an internal operational milestone, **not** an acceptable substitute for RFC3161-backed M4 completion. Current local code is a single-writer prototype: concurrent processes are not yet coordinated, directory fsync and durable failure recovery are not proven, and the host administrator can alter local evidence and clock. Do not run production without resolving these issues.

## 2026-11-08 11:04 JST run — M4.5 trusted readback
- Added `prism_ops.trusted_s3_readback.verified_s3_readback`: independently fetches pinned S3 version and provider retention, requires COMPLIANCE mode and deadline, rejects wrong version or byte hash. This is a *component*, not yet wired to the PRE acceptance boundary.
- Added six mocked adversarial regression tests and CI invocation. Commit `1f07811f2a7856d9b24189a04678f6ee7e7f5a58`; workflow result not yet observed at time of report.
- Blocking: live S3 permissions/retention, TSA nonce request-response binding and verified trust policy, forecast gate trusted readback integration, official race inputs and all-AI predictions. No live VERIFIED_PRE or settlement evidence.
- Today's official race denominator and current queue were not established by this engineering run; do not infer them from previous chat. GitHub source accessible, Notion Master search accessible; complete persistence ledger and official race inputs not verified.

## 2026-11-08 follow-up — RFC3161 parser hardening
- Reviewed canonical verifier, acceptance gate and S3 integration tests.
- Fixed regex escaping for OpenSSL request output and fixed SHA-256 hexdump parsing to include all 32 bytes across the two 16-byte rows. Local OpenSSL 3.5.5 generated a real request and the extracted digest matched SHA-256 of source bytes (component-level observed success, not full signed TSA verification).
- Replaced stale pre-provenance mocked tests with missing-request, unreadable-request and wrong-imprint rejection tests; added original request to S3 integration test fixtures.
- Commit chain: `65e556fecfdf0c5887cf2f9e85742788523e43d7`, `52dffc57e73f09b111acc6cc3901ce4ed75e7684`, `6900aacfe9936603711a45f53f6a358150588eac`, `2ba78d32536b591e149d509f173493505fda8b45`.
- **Outstanding:** CI run and complete Python suite not observed; real signed TSA positive/negative verification, pinned TSA policy/cert revocation, real S3 provider Object Lock, official race PRE, and official settlement remain blocked/unverified. Current S3 test mocks only validate the integration contract.
- **Design risk:** the trusted S3 client is still injected through a caller-controlled proof bundle; production should inject trusted provider configuration from the verifier service, not accept arbitrary client/bucket/key parameters from forecast producer.
- **Design risk:** timestamp request nonce must be generated before POST and the original request durably stored; the signed response must be validated against it. Current request binding code is not a substitute for operational issuance proof.
