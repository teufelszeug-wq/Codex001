# Phase A Residual Debt Root-Cause Analysis — 2026-10-07

## Conclusion
The remaining January gaps are not a failure of the Phase-A foundation architecture. They are historical artifact preservation and point-in-time evidence problems. Keep Phase A closed; transfer bounded work to Phase B and Phase D.

## 1. January raw replay package not recovered
Root cause:
- Historical reports reference local paths such as data/replay_202601/jra_nar_research_run_v3, but the currently searchable Library contains reports/derived CSVs rather than the complete runnable directory.
- The latest project plan also records a damaged/unusable archive attempt.
- There was no enforced artifact manifest + immutable archive rule when the historical run was created.

Countermeasure:
- Rebuild a canonical January dataset from official/public routes where legally and technically available.
- Preserve source locators, retrieval timestamps and hashes.
- Store manifests/hashes/code in GitHub; do not put uncertain-rights raw payloads in the public repo.
- Every future replay run must emit an Artifact Manifest and Execution Ledger.

Disposition: Phase B dataset reconstruction + Phase D provenance audit.

## 2. January runner raw not recovered
Root cause:
- A prior report records 11,394 NAR runner rows, but current search did not recover the raw runner file.
- Derived reports are insufficient to reconstruct every pre-race feature exactly.

Countermeasure:
- Reacquire/rebuild runner-level records from official routes.
- Join by authority/race identity and stable runner identity where available; never silently join ambiguous horses by display name.
- Produce a coverage report and explicit missingness mask.

Disposition: Phase B B0 dataset reconstruction.

## 3. Strict historical point-in-time certification 0/1,354
Root cause:
- Current official historical pages prove race/result facts, but do not by themselves prove the exact historical publication/revision time of every racecard, scratch, odds snapshot or result.
- The old replay was result-isolated as a research process, but strict contemporaneous availability was not archived per field.

Countermeasure:
- Do not try to manufacture PRE_CERTIFIED timestamps retrospectively.
- Classify each field PRE_CERTIFIED / PRE_AVAILABLE / LATE_PRE / POST_ONLY / UNKNOWN_TIMESTAMP.
- Use historical reconstruction for model research; reserve Genuine Forward claims for newly frozen snapshots.
- Future collector records observed_at / available_at / retrieved_at at ingestion.

Disposition: Phase D VAL-2. This is intentionally not a Phase-A blocker.

## 4. AI Registry unresolved names
Root cause:
- User-directed rename constraints and legacy naming conflicts are product/canon issues, not data-foundation execution failures.

Countermeasure:
- Keep stable functional IDs.
- Leave unresolved display names unresolved until a canon-safe rename is selected.
- Never block data/model execution on cosmetic persona naming.

Disposition: Phase C/E canon refinement; not Phase-A blocker.

## AI panel decision
Data reviewer: rebuild missing raw assets, do not infer them from reports.
Validation reviewer: strict PIT cannot be retroactively guaranteed; preserve uncertainty classes.
Engineering reviewer: future runs must be content-addressed and manifest-driven.
Model reviewer: B0 can begin on reconstructed canonical inputs with explicit masks.
Editor reviewer: unresolved persona display names must not block engine work.

Decision: no new major milestone. Add one bounded Phase-B subtrack: B-DATASET / January Canonical Reconstruction.
