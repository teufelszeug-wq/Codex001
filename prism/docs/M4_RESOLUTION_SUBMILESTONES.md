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

## M4 recovery replan — parser and trust-boundary audit
### Verified code changes (not production acceptance)
- Fixed remaining escaped-whitespace bug in OpenSSL request hexdump parser (`c961c4f6`).
- Reject truncated SHA-256 request imprints even if parser returns partial hex (`b71bf78f`).
- Added two focused parser regressions: complete digest proceeds to signature verification, truncated digest fails before signature verification (`0869f802`). CI result is NOT observed.
### Prioritized critical path
1. **M4.0 CI recovery:** run full Python suite and real OpenSSL fixture, repair all regressions, capture workflow SHA/log URL.
2. **M4.3 trust boundary:** configure S3 client, pinned bucket/prefix and TSA CA/policy in independent verifier service. Never accept untrusted client objects or trust anchors from forecast producer.
3. **M4.2/M4.3 live TSA:** persist original TSQ and TSR, verify SHA-256, nonce, signer chain, EKU, policy and genTime against actual signed forecast bytes. Add expired/revoked/wrong nonce adversarial cases.
4. **M4.4/M4.5 live WORM:** provider-confirmed COMPLIANCE retention, pinned version ID, independent-process readback, SHA-256 and immutable receipt envelope.
5. **M4.6/M4.7 live PRE:** official runner list, result-isolated all-AI roster, deadline scheduler, retries, single-writer concurrency control and durable journal.
6. **M4.8/M4.9 acceptance:** one genuine future race pre-off VERIFIED_PRE with retained proof, then official settlement and disaster recovery rehearsal.
### New explicit issues
- The forecast producer currently supplies `trusted_s3_client` and `trusted_tsa_ca_pem` in `proof_bundle`. This is a **trust-boundary vulnerability**, not resolved by checking hashes. Promote verifier-side dependency injection to mandatory M4.3 acceptance.
- A valid RFC3161 request/response pair does not alone prove it was issued for the race before off unless source/forecast bytes, scheduled off, and genTime are bound and independently audited.
- Unit tests and mocks are insufficient for external timestamp and cloud retention claims. CI must pass before considering code complete; real E2E must pass before M4 completion.
### Reporting
No new race_id, verified PRE or official settlement established in this engineering continuation. Official race denominator, Notion Master and complete persistent race ledger were not read in this run; classify as unverified, not zero.

## Trust-boundary remediation (current continuation)
- **Root cause prioritized:** PRE validation previously accepted caller-provided S3 client and TSA CA trust anchor, making self-attested evidence possible.
- Changed `validate_forecast(..., verifier_context=...)` and `settle_forecast(..., verifier_context=...)` to require verifier-owned S3 client, pinned bucket/prefix and TSA CA. Producer-supplied trusted client/CA fields are explicitly rejected. Missing verifier context fails closed.
- Updated S3 integration tests to inject the verifier context and added negative tests for forged client, absent context and out-of-prefix object keys.
- Commits: `a855303b557d8dc3b9ba56ca84425b73fe11343f`, `58a4132781eaa203d6abdd1888dadcfe43746430`, `34c0d06c067d3534b57aa54a5438fb7d1c857861`.
- GitHub Actions PR-triggered workflow lookup for latest commit returned no runs. **CI status not established.**
- **Important limitation:** `verifier_context` is an API argument, not an authenticated process boundary. Only a separately deployed verifier with locked-down secrets and provider permissions can establish actual independent trust.
- **Next:** verify tests in runner, enforce verifier-owned trusted configuration via process/service boundary, pin TSA signer policy and validate real signed request/response, then run live WORM and future-race acceptance.
- Official race queue, Notion master and real PRE ledger not reconciled this engineering pass; no verified new PRE/settlement.

## 2026-11-08 12:09 JST — PRE saved-at binding hardening
- Re-read canonical M4 gate, RFC3161 tests and persistent M4 ledger.
- Found that RFC3161 token genTime was checked against source_as_of and scheduled_off, but not forecast saved_at. A token issued *before* the claimed save time could therefore pass time-window validation.
- Added fail-closed `RFC3161_TIMESTAMP_BEFORE_FORECAST_SAVE` rejection in provenance verifier (commit `5c9519ada23ed36ad9fb30af756b8fd5703baf21`).
- Added regression with source 10:00 JST, saved_at 10:30 JST, token 10:15 JST, scheduled_off 12:00 JST; must reject (commit `2693d3064308a9ba449098b903ef0d96a8957c44`).
- **Verification level:** committed test, CI not yet observed; no claim that actual TSA token or WORM object was verified.
- **Priority replan:** (1) run suite on current SHA and fix regressions, (2) deploy independent verifier and pin trust policy, (3) validate live TSA and S3 WORM, (4) official future-race full AI PRE and readback, (5) official result settlement and recovery rehearsal.
- **Operations:** no newly verified PRE race_id or official settlement observed. Official denominator, Notion Master and pending race ledger remain unverified in this run, not zero.

## 2026-11-08 12:59 JST — official race identity and off-time binding
- Re-read canonical gate, RFC3161 verifier, regression tests and persistent M4 ledger.
- Root-cause vulnerability: producer-controlled `race_id` and `scheduled_off` could shift the PRE acceptance deadline. Added verifier-owned `official_race_id` and `official_scheduled_off` checks to PRE and inherited settlement gate; mismatches fail closed. Commits `2c4ad7f627d69b10231f91f197a069a9886b95cb`, `7e1feb6963941be36d7172bb9fa23c4bd26868cd`.
- Repaired stale RFC3161 regression fixtures for required original TSQ and `saved_at`; commit `1aa550cebc624653c9d6f7a84eef5bee2851a9c4`.
- Local OpenSSL request generated from bytes; extracted 32-byte imprint matched SHA256, using current parser expression. **Only request-parser component tested, not signed token or live cloud.**
- GitHub commit combined statuses for `7e1feb6` returned empty; current SHA CI PASS **not established**. Local repository clone unavailable due to DNS failure; full project suite **not executed**.
- Remaining P0: trusted official feed and reschedule/cancellation freshness must be obtained in verifier service, not from a producer-set `verifier_context`; live TSA trust policy and revocation; real provider WORM and independent readback; CI pass.
- M4 completion remains BLOCKED pending future race with genuine PRE, independent proof and official settlement. No new race IDs or official denominator verified in this engineering run.

## 2026-11-08 continuation — regression reliability and official runner binding
- Found a literal `\\n` in the mocked OpenSSL `Time stamp:` response; corrected to an actual newline so timestamp parsing is exercised. Commit `b2cb42661ef325b29a0073d3316ce3cd32008e2c`.
- Added mandatory `official_entries` in verifier-owned context and compare `(horse_no, horse_name)` against the forecast roster, preventing producer from silently changing runner identities while claiming official inputs. Commit `f94a6d2616bce9e73d53476ba5c81c55d108ed03`.
- Added negative regressions for mismatched official horse name and unavailable official runner list. Commit `ae0a955af179daf7cb9eef49b68f46c684222eec`.
- Full CI still not established. No claim of verified PRE from mocked tests.
- **Residual high-risk:** official feed freshness, scratches, reschedules and post-result exposure must be verified from trusted data in a separate process. Caller-provided `verifier_context` is not itself an independent trust boundary. Need end-to-end race deadline and result embargo.
- **Next priority:** run current suite and fix any failures; implement verifier-side official-feed ingestion and schedule change policy; validate live TSA and S3 COMPLIANCE in independent processes; process genuine future race and settle.
- Official denominator, Notion master and live race ledger not fully reconciled; no newly established real race PRE, settlement, paper or learning records.
