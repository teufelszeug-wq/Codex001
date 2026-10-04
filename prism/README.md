# PRISM Development Master Plan v3

PRISM is the integrated successor to the RIO research/prediction/newspaper system.

## 2026-10-05 restructuring

The previous roadmap had too many top-level milestones and submilestones that had grown into major workstreams. PRISM is now managed as **6 true development phases**.

VAL is not a top-level product milestone. It is the validation track inside Phase D and may audit work from other phases.

### PHASE A — Foundation & Governance
Scope:
- PRISM canon / source-of-truth policy
- AI Registry
- Source Registry / Rights Ledger
- Canonical race / runner / horse / jockey / trainer schemas
- RAW -> NORMALIZED -> FEATURE
- Entity Resolver
- provenance / timestamp / schedule mutation ledger
- GitHub / Notion governance

Exit gate:
Inputs can be frozen as auditable manifests with traceable IDs, provenance and timestamps.

### PHASE B — Core Prediction Engine
Scope:
- Base Ability
- Course / Surface / Class normalization
- State / Recency / Rotation
- Pace
- TBI / SSI / Track Bias
- Workout / Condition
- Jockey
- Specialist Intelligence / N-Value
- Monte Carlo / Probability
- Calibration
- Market / Value / Bet Optimizer

B0-B11 are model ablation levels, not milestones.

Exit gate:
One race can be processed reproducibly from canonical input to True Probability, Value and bet candidates.

### PHASE C — Deliberation & Learning
Scope:
- Specialist Output Schema
- Evidence Ledger
- Position Ledger
- PRE / POST M-DISC
- counterargument / minority opinion / pre-mortem / hindsight gate
- Learning Ledger
- Candidate -> Shadow -> Adopt / Reject
- delayed-learning control
- drift monitoring

Exit gate:
Expert reasoning and post-race learning are traceable and reproducible without hindsight leakage.

### PHASE D — Validation & Research
Validation Track:
- VAL-0 Foundation
- VAL-1 Universe
- VAL-2 Temporal Firewall
- VAL-3 Replay & Learning
- VAL-4 Model Completion
- VAL-5 Historical Control
- VAL-6 Genuine Forward

Research:
- January 2026 research replay
- February+ historical controls
- B0-B11 ablation
- coverage-matched comparisons
- calibration / ROI / MaxDD / block bootstrap / drift
- genuine forward Golden Snapshots

Exit gate:
Historical reconstruction and genuine forward evaluation are both reproducible and clearly separated.

### PHASE E — M-PAPER / Publishing
Scope:
- M-PAPER v1.4 Canonical Spec
- front page
- full racecard
- Prediction & Expert Commentary
- Visual / Data Analysis
- Roundtable
- Result Review
- Morning / Final / Result-Review publication bundle
- PDF / PNG / Web-ready output
- Golden Screenshot / Layout QA

Paper-specific milestone IDs remain a Paper Track, not top-level PRISM milestones.

Exit gate:
Publication bundles are generated automatically from real PRISM outputs and pass critical QA.

### PHASE F — Product, Automation & Release
Scope:
- PRISM Reader / Dashboard
- PC / mobile / web
- race search / comparison / archive
- AI performance table
- Morning Lock / Final Lock
- result ingest
- scheduler / monitoring / retry / reproducibility
- Forward Golden Ledger
- PRISM v1.0 release gate

Exit gate:
Daily operations run end-to-end with critical leakage=0, reproducibility and traceability.

## Old -> New mapping

- old M0-M1 -> Phase A
- old M2-M6 -> Phase B
- old M7 + old M9 + specialist deliberation -> Phase C
- old M8 + old M14 -> Phase D
- old M10-M11 -> Phase E
- old M12-M13-M15 -> Phase F

This compresses 16 top-level milestones into 6 true development phases.

## Current status

| Phase | Estimated maturity | Status |
|---|---:|---|
| A Foundation & Governance | 50-60% | IN PROGRESS |
| B Core Prediction Engine | 30-40% | IN PROGRESS |
| C Deliberation & Learning | 35-45% | DESIGN + PARTIAL IMPLEMENTATION |
| D Validation & Research | 40-50% | ACTIVE |
| E M-PAPER / Publishing | 65-75% | ADVANCED DESIGN + PROTOTYPE |
| F Product / Automation / Release | 15-25% | EARLY |

Overall dependency-weighted maturity: approximately 40%.

Publishing/design artifacts are ahead of the prediction engine, so artifact volume is higher than actual product completion.

## Recorded evidence

- January research universe: JRA 276 + NAR 1,078 = 1,354 races.
- Existing reports record limited research replay 1,354/1,354.
- Strict historical point-in-time certification remains open.
- Existing report records NAR 11,394 runner rows, but the raw runner package is not currently recovered.
- Legacy RIO master records tested prediction-registry / market-separation / 100-yen settlement components.
- N-Value production specification exists.
- M-PAPER v1.4 canonical spec and golden fixtures exist.
- Exact Full PRISM B0-B11 reproduction on all 1,354 races remains open.

## Critical path

Phase A
-> Phase B
-> Phase D
-> Phase C
-> Phase E
-> Phase F

Phase C and Phase E can continue in parallel, but production approval depends on B and D.

## Immediate execution order

1. Close Phase A candidates: January canonical rebuild, Asset Recovery Ledger, Feature Coverage Census.
2. Reproduce B0 on 1,354/1,354.
3. Execute B2/B3/B4/B7 -> B1/B5/B6/B8 -> B9 -> B10 -> B11-O.
4. Close VAL-4 and run VAL-5 February Historical Control.
5. Start genuine-forward snapshots on unused future races.
6. Connect specialist contribution / M-DISC / Learning Ledger to real race data.
7. Feed real PRISM outputs into M-PAPER.
8. Build automation / web product / release gate.

## Status semantics

Every artifact is tracked as:
- DESIGN
- IMPLEMENTED
- EXECUTED
- VERIFIED
- PRODUCTION

A spec is not implementation.
Code is not execution.
A successful run is not production.

## Source-of-truth policy

- GitHub: code, schemas, manifests, tests, reproducible run logs and audit artifacts.
- Notion: roadmap, phase status, decisions, risks and cross-chat progress.
- ChatGPT Library: legacy artifact migration source, not long-term source of truth.

## Cross-chat consolidation rule

Work performed in other PRISM/RIO chats must be mapped into one of the six phases above.

Before adding a new submilestone, check whether it can instead be represented as:
1. an existing phase checklist item,
2. an acceptance criterion,
3. or a module-level task.

Do not create a new milestone unless it is truly an independent development phase.
