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

## 2026-11-08 follow-up — official feed freshness and result embargo
- Re-read gate, integration regressions and persistent M4 ledger; fixed a production-blocking fail-open path: verifier-owned official race context did not require a fresh observation or result/cancellation embargo.
- Added required `official_as_of` (timezone aware; not after saved_at; strictly before official off; at most 15 minutes old), `official_result_exposed is False`, and `official_race_cancelled is False`. Fail-closed error labels `OFFICIAL_FEED_TIME_UNVERIFIED`, `OFFICIAL_FEED_AFTER_PRE`, `OFFICIAL_FEED_STALE`, `OFFICIAL_RESULT_EXPOSURE_UNVERIFIED`, `OFFICIAL_RACE_STATUS_UNVERIFIED`. Commit `9c5b1a18325b83f29cb8d269c0e89308d9ec8f59`.
- Added regression cases for stale feed, result exposure, cancellation and missing official feed time; commit `bd61036d00f1833bea6a443f2255240ed1f156fa`.
- **Limitations:** 15-minute freshness is an interim engineering threshold, not a substitute for trusted provider update semantics or cancellation polling at deadline. Verifier context remains in-process injectable. Real provider official feed, external TSA, WORM, current-SHA CI, and actual future-race E2E remain unverified.
- **Next critical path:** CI full suite with saved logs; independently authenticated official feed and race deadline; TSA signer policy and real signed request; WORM provider readback; scheduler and real race PRE.
- Local checkout via GitHub HTTPS DNS lookup failed, so full suite was not run in this continuation. Do not mark CI PASS or M4 complete. No newly verified race, settlement, paper or learning.

## 2026-11-08 13:04 JST — actual CI failure diagnosis and repair
- Re-read canonical M4 gate, RFC3161 verifier, integration tests and ledger; queried Notion Master index. Notion master page located at https://app.notion.com/p/3ed76efc40298187abd8fd105b2d5a76?pvs=204 but its full contents and race queue were not reconciled.
- Retrieved **actual failed GitHub Actions run 42445223031** (job 128622614716) for prior SHA `8a1a75ad`: 25 tests, 6 failures, 1 error. CI log: https://github.com/teufelszeug-wq/Codex001/actions/runs/42445223031 .
- Root cause: legacy `test_m4_provenance_verifier.py` omitted mandatory original TSQ and saved_at, and old mocked subprocess sequence lacked the SHA-256 query stage. Repaired tests to provide full SHA256 query output, original TSQ, saved_at, and signature/reply sequence; commit `29746b756c1e3f4794772879d06b9d0a65949a02`.
- Another legacy signed-byte mismatch regression failed because new verifier-owned S3 context was absent. Repaired test with pinned S3 retention/readback mock and verifier-owned official race context, preserving mismatch assertion; commit `a06760abf0773433dd8d8adb9c2b639d9f9f5311`.
- **Do not mark M4.0 PASS:** current commit has no workflow run returned yet; follow up with fresh CI logs and further fixes. Mock tests do not prove live TSA or provider WORM.
- Official race denominator and valid PRE queue not established; no new PRE, settlement, paper or learning record. Next priority: CI PASS, independent official feed, real TSA and S3 WORM, then live pre-off E2E and settlement.

## 2026-11-08 CI failure root-cause recovery — verified workflow logs
- Retrieved actual GitHub Actions workflow **42445223031**, job **128622614716**, conclusion **failure**. At SHA `8a1a75ad`, `test_*provenance*.py` executed **25 tests: 6 failures and 1 error**. This supersedes previous "CI unknown" notes for that SHA. The workflow stopped at the first failing command, so other suites were not run in that attempt.
- Six failures/one error were stale fixtures and tests after mandatory original RFC3161 TSQ and verifier-owned context. Updated `test_m4_provenance_verifier.py` request fixture, actual line breaks and third subprocess invocation for timestamp; commits `3c08da60`, `00d58c71`. Updated `test_pre_provenance_contract.py` to mock independently verified S3 readback and supply trusted context while asserting byte mismatch; commit `2b69443a`.
- CI workflow previously omitted newly added S3 acceptance and RFC3161 imprint regression suites; added both to `.github/workflows/prism-m4-contract.yml`, commit `9bc3fcaf`.
- **No claim of successful rerun:** workflow run for `9bc3fcaf` was not yet returned at inspection time. Monitor new run and repair actual failures before proceeding. CI PASS for current SHA remains UNVERIFIED.
- Prioritized next: (1) capture new workflow result/logs and fix remaining failures, (2) independent trusted official feed and snapshot runner, (3) live TSA and WORM provider, (4) actual future race PRE and official settlement. No new live race accepted in this continuation.

## 2026-11-08 consolidated cross-system status (Notion/GitHub reconciliation)

### Sources of truth and name mapping
- Notion [6-PHASE Master](https://app.notion.com/p/3ed76efc40298187abd8fd105b2d5a76) is the project-governance canonical record. Phase A (data and identity), B (model and ticket), C (deliberation and learning), D (temporal audit and performance validation), E (M-PAPER), F (daily operations and production). `M4.0–M4.9` remains a **cross-phase forecast-provenance acceptance track**, not an additional top-level Phase and not equivalent to the historical model M4.
- GitHub `prism/src`, tests, schema, immutable manifests and actual CI outputs govern implementation claims. Notion `WORKING`/partial Golden report titles alone must not be counted as externally VERIFIED_PRE.
- GitHub **PR #7** is Draft and unmerged into `main`. Its head at inspection was `1174e96bf46d973a9972b6f7e7d9ade7de3df977`; branch code must not be described as deployed or merged.
- The current commit has real successful contract CI: Actions **42445561997 (pull_request)** and **42445557670 (push)**, both conclusion `success` on `1174e96b` at 2026-11-08 **13:08 JST**. This supersedes historical CI pending/failure entries **for this SHA only**. Those prior entries remain as historical execution evidence.
- The CI workflow executes selected mocked/contract Python test suites, **not an exhaustive repo-level test suite**, real TSA, real S3 WORM, or a genuine future-race operation. Therefore M4.0 **selected contract CI PASS**, but M4 overall remains **NOT VERIFIED/NOT PRODUCTION**.

### P0 acceptance blockers (must not declare complete)
1. Independent, authenticated official JRA/NAR schedule, runner, scratch and result-embargo ingest with time provenance.
2. RFC3161 real TSQ/TSR issuance, CA/certificate EKU/policy/revocation, nonce and signed genTime proof.
3. Real provider S3 Object Lock COMPLIANCE, version ID, retention, and independent-process pinned readback.
4. Automated pre-off final forecast containing all registered AI marks, names, 100-yen tickets or explicit pass, followed by post-result official settlement and traceable audit.
5. Durable scheduler, clock trust, retry/crash recovery and monitoring.

### Status definitions and evidence policy
- `DESIGN` = specified; `IMPLEMENTED` = committed; `EXECUTED` = an identified run with artifacts; `VERIFIED` = independently checked acceptance evidence; `PRODUCTION` = sustained live acceptance.
- A green mocked contract CI must not be promoted to `VERIFIED_PRE`. Historical records with `WORKING`, `PRE-ODDS`, `partial Golden` or `RUN` labels remain separate from RFC3161+WORM backed races until matching proof bytes and chain are demonstrated.
- Published public GitHub must not receive credentials or rights-restricted raw official data.
- Report official race denominator, genuine pre-off VERIFIED_PRE, full-AI picks, official settlement, per-agent ROI, completed newspapers, actually measured learning and exact persistent locations separately; missing/unknown is `UNVERIFIED`, not zero.

### Current verified inspection
- Latest observed GitHub CI: PASS on `1174e96b` (run 42445561997). PR draft and unmerged.
- No additional genuinely authenticated future-race VERIFIED_PRE, official settlement, newspaper completion or learning event established during this reconciliation.
- Existing Notion MASTER content dates to at least 2026-11-06; previous Oct Snapshot entries were explicitly mixed `WORKING`/partial Golden, not evidence for present live M4 success.

### Cross-system workflow
- **Plan**: Notion 6-Phase Master + M4 acceptance subsection.
- **Build**: GitHub branch and code review PR #7; update versioned tests/contracts/manifest.
- **Check**: GitHub Actions with exact SHA and run ID; separate external evidence packet for TSA/WORM.
- **Operate**: future official race inputs → independent pre-off snapshot → verified timestamp/WORM → results embargo → official settlement.
- **Publish**: Notion status from observed GitHub evidence, with record date and links, without overwriting historical runs.

## 2026-11-08 — GitHub CI error log verified and patched
- Read GitHub Actions **run 42445419461**, job **128623198979**, conclusion **failure**. First suite executed **25 tests: 24 passed, 1 failed**. Sole failure `test_reject_mocked_timestamp_after_off` due to a *literal backslash-n* in the mock timestamp output; `RFC3161_TIME_UNPARSEABLE` occurred before the intended after-off rejection. Corrected fixture to actual newline, commit `22e065c3`.
- Reviewed trusted S3 object key policy; fixed prefix-confusion case by requiring a slash-terminated verifier-owned `key_prefix` (e.g. `pre/` not `pre`); commit `c552a9eb`. Added adversarial regression `test_prefix_without_path_boundary_rejected`, commit `195e522f`.
- Verified local container cannot resolve `github.com` via git HTTPS, so direct local checkout/full suite remains blocked. Current SHA workflow success not observed; **do not claim CI PASS**.
- External prerequisites still pending: trusted official feed and deadline scheduling, independent verifier service boundary, actual TSA issuance and certificate validation, real COMPLIANCE Object Lock retention/readback, genuine pre-off all-agent forecast and official settlement.
- Official race denominator and Notion master not reconciled in this code-only run. New genuine PRE 0R; settlement/paper/learning not verified.
