# PRISM status — 2026-10-08

The six phases in ../README.md remain the master plan. This update is an
organization/integration task within Phase A, not a seventh milestone.

| Phase | Evidence-backed status | Next acceptance gate |
|---|---|---|
| A Foundation | Foundation gate VERIFIED in current GitHub handoff; historical data debt remains | Recover January archive, establish canonical race/runner IDs and feature coverage |
| B Prediction | Legacy component reports exist; full engine reproduction unverified | Reproduce B0 on the canonical 1,354-race universe, then the documented ablation sequence |
| C Deliberation | M-DISC 1.1 structural audit imported; synthetic regression tests available | Real-race evidence, approved AI roster, five independent discussions and semantic review |
| D Research | January 1,354 races reported; raw replay not revalidated here | Recover archive, reconcile universe, distinguish historical reconstruction from genuine forward tests |
| E Publishing | M3 vertical-layout prototype reported and partially inspected | Publish from actual engine/discussion output; all-page content and layout acceptance |
| F Product | No new implementation in this change | Depends on accepted upstream pipeline; reader/web remains later work |

## Completed scope of this integration candidate

- Preserve the master six-phase plan and map the former DISC/M4.6a task to C.
- Establish code/tests/docs/manifests/reports separation without moving other projects.
- Provide one standard-library verification command for 15 regression tests and
  five legacy function tests, plus the duplicate-session reproduction.
- Track known source artifacts without publishing private download links or raw data.
- Keep code verification, real-race execution, and production approval separate.

This closes the scoped organization task only after repository diff verification.
It preserves the existing Phase A foundation completion; it does not close Phase C, E, or the PRISM release gate. A pull request is not
a merge; main integration and production deployment remain separate decisions.

## Immediate work order

1. Recover a normally readable January archive; preserve the original unchanged.
2. Reconcile JRA 276 + NAR 1,078 and build canonical/feature coverage manifests.
3. Reproduce B0 and continue the master B-level/VAL acceptance sequence.
4. In parallel, reconcile legacy/candidate AI names with the current registry and execute five evidence-linked meetings
   for one real race. Synthetic software tests never increase meeting totals.
5. Feed accepted output to the vertical newspaper; do not substitute QA prose
   for racecards, predictions, or reporting.

January research completion is report-backed, not newly recomputed. Strict
point-in-time certification was reported as 0/1,354. February completion is not
established. Missing proof is UNKNOWN/BLOCKED, not an invented completion count.

## Known audit limitations

Structural validation does not establish source authenticity, semantic relevance,
independent reasoning, or model improvement. Near-duplicate prose and input-shape
hardening remain open. Caller-supplied timestamps are not external attestation.
The legacy daily orchestrator is not a production temporal firewall or a completed
learning pipeline. No real-race or 100,000-iteration achievement is claimed.

## Fixed requirements

100 yen per ticket; separate frame number and horse number; document Bias signs;
separate probability from market Value. Rio remains a rookie female reporter,
not editor-in-chief. Preserve full-AI/full-horse reasoning, minority opinions,
five distinct discussion themes, and vertical-first newspaper layout.

## Concurrent update reconciliation

Base commit: 74c988edadd9111a46ceaa14f2e26cc813c104fe. The Phase A foundation
completion record and executable pipeline were added by another workstream and
are preserved. Existing canon/schema/roadmap files remain authoritative.
The new assets.json is a hash supplement to docs/roadmap/PHASE_A_ASSET_RECOVERY.md,
not a competing recovery ledger. The AI registry exists, but legacy/candidate
names and updated role instructions still require reconciliation before all-AI execution.

Foundation test rerun: the committed test used a stale sibling import. Updated
its path to ../../src/foundation/pipeline.mjs. Seven assertions now pass; the
console count was corrected from six to seven. Evidence: reports/foundation-verification.json.
Run: node tests/foundation/pipeline.test.mjs from prism/.

## Review fixes — 2026-10-08

Both automated review findings addressed: result-revealed snapshots are rejected
before any pre-race archive writes, and required dialogue moves must occur in
order (intervening discussion is allowed). Added three regression tests.
M-DISC: 15 unittest cases plus five legacy function checks pass.
Foundation: seven assertions passed in the prior integration check.
This verifies the scoped organization/audit integration; Phase B dataset
reconstruction, semantic acceptance and production operation remain separate.
