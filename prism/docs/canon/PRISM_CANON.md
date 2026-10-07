# PRISM Phase A Canon v0.1

Status: IMPLEMENTED (governance artifact), not Phase-A COMPLETE
Date: 2026-10-07

## Canon hierarchy
1. GitHub `prism/docs/canon/*` and executable schemas/manifests: implementation source of truth.
2. Notion PRISM master: roadmap/status/decision source of truth.
3. ChatGPT Library: legacy migration/evidence source; never silently overrides current canon.

## Status contract
DESIGN -> IMPLEMENTED -> EXECUTED -> VERIFIED -> PRODUCTION.
No status promotion without evidence.

## Data invariants
- NO SNAPSHOT = NO BACKTEST.
- Historical Reconstruction != Genuine Forward Validation.
- PRE data and MARKET data remain separated until probability lock.
- Prediction, Market and Result snapshots are immutable/versioned.
- Unknown data is represented explicitly; never silently impute zero/mean.
- One stated betting selection = JPY 100 for standard settlement.
- Same source payload is content-addressed and reused.

## Canonical identity
`race_id` is the primary race identity. Runner identity must not be joined only by display name when a stable authority ID is unavailable; ambiguous joins remain AMBIGUOUS_ID.

## Temporal classes
PRE_CERTIFIED / PRE_AVAILABLE / LATE_PRE / POST_ONLY / UNKNOWN_TIMESTAMP.

## Reuse key
Preferred artifact reuse key:
`authority + race_id + source_id + available_at + content_hash + schema_version`.

## Pipeline
DISCOVER -> INGEST -> VALIDATE -> NORMALIZE -> FEATURE -> PREDICT -> DISCUSS -> LOCK -> MARKET -> BET -> PUBLISH -> RESULT -> REVIEW -> LEARN.

A downstream node reruns only when one of its declared upstream hashes changes.

## Phase A exit gate
Phase A is VERIFIED only when:
- canonical schemas exist;
- source/provenance contract exists;
- identity rules exist;
- artifact manifest/cache contract exists;
- schedule mutation ledger exists;
- January canonical asset inventory is complete enough to reproduce B0 or explicitly records missing assets;
- representative pipeline run is deterministic.
