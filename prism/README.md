# PRISM Development Master Plan v2

PRISM is the integrated successor to the RIO research/prediction/newspaper system.

## Major milestone structure

The previous 16 top-level milestones were too granular. PRISM is now managed with **8 major milestones**. VAL remains a validation subsystem, not a top-level product phase.

### M0 Project Canon & Governance
Canonical specs, AI Registry, Source/Rights Registry, data contracts, naming/versioning, GitHub/Notion operating rules.

### M1 Data & Temporal Foundation
JRA/NAR/Banei universe, runners, entity resolution, past performance, course/weather/track/bodyweight/workout, provenance and timestamps.
RAW -> NORMALIZED -> FEATURE.

### M2 Prediction Intelligence Engine
Core Ability + Course + State/Recency + Jockey + Pace + Bias + Condition + N-Value + VIDEO + WORKOUT + BLOOD.
Former B0-B8 are internal feature/ablation levels, not major milestones.

### M3 Probability, Market & Decision Engine
Ability distributions -> Monte Carlo -> Calibration -> True Probability -> Market -> Value -> Bet Decision.
Former B9/B10/B11 are internal implementation levels.

### M4 Deliberation & Learning System
PRE/POST M-DISC, evidence/position ledgers, counterargument, minority opinion, failure taxonomy, shadow learner, delayed learning and model promotion.

### M5 Validation & Research Program
PRISM-VAL lives here:
- VAL-0 Foundation / Reproducibility
- VAL-1 Universe / Coverage
- VAL-2 Temporal Firewall
- VAL-3 Replay / Learning
- VAL-4 Model Completion / Ablation
- VAL-5 Historical Control
- VAL-6 Genuine Forward

### M6 Publication & Product
M-PAPER + Web Reader + Dashboard.
Paper-specific M1.x/M3.x/M11.x/M13.x IDs remain only as Paper Track IDs.

Paper Track:
- P1 Racecard / Typography
- P2 Prediction / Expert Commentary
- P3 Visual / Data Analysis
- P4 Roundtable / Result Review
- P5 Production QA / Golden Regression
- P6 Web / Reader

### M7 Automation, Operations & Release
Scheduled ingest, Morning/Final locks, result ingest, review, learning, publication, monitoring, recovery, genuine forward operation, PRISM v1.0 release.

## Old -> New mapping
- old M0 -> M0
- old M1 -> M1
- old M2 + M3 -> M2
- old M4 + M5 + M6 -> M3
- old M7 + M9 -> M4
- old M8 -> M5
- old M10 + M11 + M12 -> M6
- old M13 + M14 + M15 -> M7

## Current verified/reported state
- January research universe: JRA 276 + NAR 1,078 = 1,354 races.
- Existing reports record limited research replay 1,354/1,354; this was not Full PRISM and strict historical point-in-time certification remains open.
- Existing report records NAR 11,394 runner rows, but the raw runner package is not currently recovered.
- N-Value production specification exists.
- M-PAPER v1.4 canonical spec exists.
- Historical paper-track artifacts include M11 structure complete / M11.5 baseline pass, plus later visual analytics work.
- Exact B0 predictor rerun and full B0->B11 ablation are not yet reproduced from recovered raw assets.

## Critical path
1. M1: January canonical rebuild
2. M2: B0 exact reproduction for 1,354/1,354
3. M2: feature/specialist implementation and ablation
4. M3: probability -> market -> Full PRISM
5. M5: VAL-4 closure / VAL-5 February control
6. M6: connect real PRISM outputs to M-PAPER
7. M7: genuine forward automation and release

## Progress semantics
Every major milestone is tracked using:
- DESIGN
- IMPLEMENTED
- EXECUTED
- VERIFIED
- PRODUCTION

A submilestone is promoted only if it:
- spans multiple major milestones,
- owns an independent product/artifact/operation,
- has independent dependencies,
- or becomes too large to manage within its parent.

Feature blocks, ablations, QA gates, paper components and VAL branches remain submilestones.

## Repository structure
```
prism/
  README.md
  docs/
    canon/
    decisions/
    roadmap/
  schemas/
  src/
  tests/
  validation/
    val0-foundation/
    val1-universe/
    val2-temporal-firewall/
    val3-replay-learning/
    val4-model-completion/
    val5-historical-control/
    val6-forward/
  data/
    manifests/
  artifacts/
    audits/
    runs/
  newspaper/
  ops/
```

## Source-of-truth policy
- GitHub: code, schemas, manifests, tests, reproducible run logs and audit artifacts.
- Notion: roadmap, milestone status, decisions, risks and AI-panel summaries.
- ChatGPT Library: migration source for historical artifacts; not the long-term canonical source.

Any PRISM/RIO work performed in separate chats should be mapped back into these 8 major milestones before progress is reported.
