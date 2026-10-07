# Phase A Short AI Panel Review — 2026-10-07

This is a **short panel generated for this Phase-A review**. It is not the 100k-character M-DISC training/audit.

## Data / provenance reviewer
Claim: Phase A should close around a canonical manifest, not around “we collected lots of files.”
Challenge: January has strong report-level evidence but missing raw assets.
Decision: adopt Asset Recovery Ledger and forbid promotion from report evidence to raw VERIFIED.

## Pipeline / engineering reviewer
Claim: repeated JRA/NAR collection, VAL ingestion and M-PAPER ingestion must be one pipeline.
Challenge: a global cache can reuse stale data if schedule mutations or late corrections are ignored.
Decision: cache keys include source identity, availability timestamp, schema/code version and upstream hashes; schedule/result mutations invalidate only affected descendants.

## Validation reviewer
Claim: temporal certification is a separate dimension from data completeness.
Challenge: requiring PRE_CERTIFIED for all historical fields would stop useful reconstruction.
Decision: retain PRE_AVAILABLE/LATE_PRE/POST_ONLY/UNKNOWN_TIMESTAMP and allow research reconstruction while preventing genuine-blind claims.

## Publishing / rights reviewer
Claim: the public GitHub repository must not become a raw-data dump.
Challenge: reproducibility needs source evidence.
Decision: commit schemas/manifests/hashes/locators and derived audit artifacts; raw licensed/uncertain-rights data stays outside public GitHub.

## Editor / project reviewer
Claim: do not add another top-level milestone for pipeline/cache.
Challenge: pipeline work is substantial.
Decision: add **A-Pipeline** as a Phase-A subtrack only. It contains Collector, Artifact Cache, Dependency Graph, Incremental Runner and Execution Ledger.

## Adopted plan change
Add one Phase-A subtrack:
**A-Pipeline — Shared Data & Incremental Execution**.
This is a subtrack, not a seventh major phase.
