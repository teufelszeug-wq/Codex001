# Phase B Start — B0 Canonical Reconstruction Plan

Status: ACTIVE

## B-DATASET — January Canonical Reconstruction
This is a Phase-B subtrack, not a new major milestone.

### Inputs
- official JRA/NAR race/result routes
- recovered January settlement/comparison artifacts
- legacy reports as evidence/indexes, never as silent substitutes for missing raw fields

### Outputs
1. race_universe manifest: expected 1,354 research races, subject to official crosscheck
2. runner canonical table
3. feature availability/missingness matrix
4. temporal-class matrix
5. B0 input dataset
6. dataset manifest + SHA-256
7. reconstruction audit

### Gates
B-DATASET-1 Universe: race_id unique; JRA/NAR totals reconciled.
B-DATASET-2 Runner: duplicate/ambiguous identity checks; missingness explicit.
B-DATASET-3 Temporal: no POST_ONLY field enters B0 prediction inputs.
B-DATASET-4 Determinism: same dataset build -> same manifest/hash.
B-DATASET-5 Baseline Ready: B0 required fields reach declared coverage threshold or a coverage-matched subset is frozen.

## B0
B0 is Base Ability only. It must not silently consume market, result, same-race post-event, or Full-PRISM specialist features.

Required outputs per race:
- runner probabilities/scores
- top pick
- confidence/uncertainty
- input manifest hash
- model/config hash
- prediction hash

Evaluation is downstream and separated from prediction lock.

## Next after B0
B2/B3/B4/B7 -> B1/B5/B6/B8 -> B9 -> B10 -> B11.
