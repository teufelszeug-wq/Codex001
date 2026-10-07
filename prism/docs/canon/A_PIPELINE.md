# A-Pipeline — Shared Data & Incremental Execution v0.1

Status: IMPLEMENTED as architecture contract; runner code not yet EXECUTED.

## Modules
1. Collector — discovers/fetches source payloads and records provenance.
2. Artifact Cache — content-addressed storage index.
3. Dependency Graph — declares upstream/downstream artifact relationships.
4. Incremental Runner — skips valid unchanged nodes and reruns invalidated descendants.
5. Execution Ledger — records run_id, code/schema versions, hashes, status and reason.

## Node contract
Each node receives only declared upstream artifacts and produces a versioned artifact manifest.

### Skip
A node is SKIPPED_CACHE_HIT when:
- all upstream hashes match;
- schema_version matches;
- code_version matches;
- artifact exists and passed its validation gate;
- no explicit invalidation/force flag exists.

### Invalidate
Invalidate affected descendants on:
- schedule mutation;
- scratch/runner mutation;
- corrected official payload;
- source hash change;
- schema/code change;
- temporal classification correction.

## Race pipeline
DISCOVER
-> INGEST
-> VALIDATE
-> NORMALIZE
-> FEATURE
-> PREDICT_PREMARKET
-> DISCUSS_PRE
-> PROBABILITY_LOCK
-> MARKET_INGEST
-> VALUE_BET_LOCK
-> PUBLISH
-> RESULT_INGEST
-> REVIEW
-> LEARN_CANDIDATE

Historical replay may stop or branch where temporal evidence is insufficient. Genuine Forward must never consume RESULT_INGEST before its pre-race locks.

## Consumers
Prediction, M-DISC, VAL and M-PAPER consume the same versioned NORMALIZED/FEATURE artifacts rather than recollecting race facts independently.

## Phase A acceptance test
A representative race run twice with unchanged inputs must produce:
- same artifact hashes;
- second run cache hits for unchanged deterministic nodes;
- no mutation of prior snapshots;
- an Execution Ledger explaining every run/skip.
