# PRISM Development Master Plan

PRISM is the integrated successor to the RIO research/prediction/newspaper system.

## Milestone hierarchy
VAL is not a top-level product milestone. It is the validation sub-system under M8 and may be applied across other milestones.

### M0 Governance / Canon
Canonical specs, AI Registry, source/rights registry, naming/versioning, GitHub/Notion operating rules.

### M1 Data Foundation
JRA/NAR race universe, runners, entity resolution, past performance, course/weather/track/bodyweight/workout.
RAW -> NORMALIZED -> FEATURE with provenance and timestamps.

### M2 Core Ability Engine
Base Ability, course, recency/state, jockey, running style and pace foundations. Includes cross-course normalization.

### M3 Specialist Intelligence
N-Value, VIDEO, WORKOUT, BLOOD, JOCKEY, COURSE, BIAS, PACE, State/Recency/Condition and specialist contribution ledgers.

### M4 Probability / Simulation
Ability distributions, Monte Carlo race simulation, Win/Top2/Top3 probabilities, uncertainty, scenario robustness and calibration.

### M5 Market / Value / Betting
Unlock market data only after ability/probability snapshot lock. ValueRatio, EV, FFI, Dark Horse, bet/portfolio engine.

### M6 Full PRISM Engine
Integrated model. B11-O Observable Full, B11-C Coverage-Matched Full, B11-F Fully Certified.

### M7 M-DISC / Deliberation
Pre/post-race structured specialist debate, evidence/position ledgers, counterargument, minority opinion, hindsight controls.

### M8 Validation / PRISM-VAL
- VAL-0 Foundation
- VAL-1 Universe
- VAL-2 Temporal Firewall
- VAL-3 Replay & Learning
- VAL-4 Model Completion
- VAL-5 Historical Control
- VAL-6 Genuine Forward

### M9 Learning / Model Governance
Post-race review, failure taxonomy, Candidate -> Shadow -> Adopt/Reject, drift and delayed-learning controls.

### M10 Newspaper Data Integration
Feed predictions/evidence into M-PAPER Morning / Final / Result-Review editions.

### M11 M-PAPER Production
Automated v1.4 canonical newspaper production and publication bundles.

### M12 Product / UI
PC/mobile/web reader, dashboards, search, race comparison, AI performance, archives.

### M13 Automation / Operations
Scheduled ingest, Morning Lock, Final Lock, results, post-race review, newspaper generation, monitoring and reproducibility.

### M14 Production Forward Validation
True pre-result forward validation on future unused races with Golden Snapshots.

### M15 Release / v1.0
Integrated release gate: critical leakage=0, reproducibility, traceability, prediction/newspaper/UI/operations complete.

## Current evidence/status
- January research universe: JRA 276 + NAR 1,078 = 1,354 races.
- Existing reports record limited research replay 1,354/1,354; this was not Full PRISM and strict historical timestamp certification remains open.
- Existing report records NAR 11,394 runner rows, but raw runner package is not currently recovered.
- M-PAPER v1.4 canonical spec exists.
- N-Value production specification exists.
- Exact B0 predictor rerun and B0-B11 full ablation are not yet reproduced from raw assets.

## Immediate priority
1. M0: establish PRISM canonical home in GitHub + Notion.
2. M1: rebuild January canonical dataset and feature store.
3. M2: reproduce B0 for 1,354/1,354.
4. M2-M6: B2/B3/B4/B7 -> B1/B5/B6/B8 -> B9 -> B10 -> B11-O.
5. M8: use VAL-4 / VAL-5 to verify model completion and February historical control.
6. M14: start genuine forward snapshots for future races.

## Repository structure
```
prism/
  README.md
  docs/
    PRISM_MASTER_PLAN.md
    canon/
    decisions/
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
- GitHub: code, schemas, manifests, reproducible run logs and audit artifacts.
- Notion: roadmap, milestone status, decisions, risks and meeting/AI-panel summaries.
- ChatGPT Library: migration source for historical artifacts, not the long-term canonical source.
