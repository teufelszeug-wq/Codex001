# PRISM operational completion contract — 2026-11-06

Status: SPECIFICATION / NOT PRODUCTION. Applies to existing Phase B/C/D/E/F, not a new top-level milestone.

## Evidence of the failure
Existing daily loop reports roundtable turns and review events while zero official pre-race forecasts, zero independently verified forward locks, and zero official settled bets can remain. These counters must not imply forecast completion.

## Pre-race priority order
1. Enumerate JRA/NAR races and off times from available official information; record source, retrieval time and missingness.
2. For each race, reuse horse/jockey data and complete runner diagnosis once per information version. No same-input repeat for quota.
3. Have every participating specialist present (a) evidence with source and as-of time, (b) its own full marks, (c) explicit 100-yen tickets OR an explicit pass, (d) doubts and counterarguments. Shinomiya Ritsu chairs; Rio asks and gives her own final marks/tickets.
4. Freeze the editorial marks, tickets, rationale, budget, input hash, model version and timestamp *before off*. Do not block on absent odds, video, photos or weather: label missing inputs and freeze a PRE-ODDS forecast. A late revision is a new immutable version.
5. Once PRE forecast exists, create the newspaper-ready roundtable transcript, data visualizations and video frame citations when licensed/available. Newspaper PDF/PNG/Web are a separate Phase E acceptance gate.
6. After official results: settle every valid PRE ticket with the official 100-yen dividend and refund rules. Publish stake, payout, net, ROI for each agent and editorial; skipped races have null ROI. Never call historical post-result picks forward tests.
7. Record diagnosis errors, disagreement, rejected minority predictions, model candidate changes and shadow comparison. No 'learning' without an applied and independently measured update.

## Non-negotiable gates
- Every race: marks + tickets/pass + pre-off timestamp + reproducible content hash, otherwise NOT_FORECAST_COMPLETE.
- Every agent: independent position and tickets/pass; an aggregate editorial pick is not a substitute.
- Evidence: URL/locator, observed_at, available_at, rights, exact statistic or clip time; never claim unseen photos/videos were analyzed.
- Market features separated from pre-market ability and probabilities.
- Snapshot hash is tamper-evidence, NOT proof of external trusted timestamp.
- Roundtable complete requires all five themes, all participating agents' conclusions and ticket choices, editorial conclusion, and publication transcript. Count real characters/events only.
- Full PRISM Phase F release requires actual forward coverage, official settlement, reproducibility, leakage QA, publication visual QA and operational reliability.

## Cross-phase milestone acceptance
A: official race/runner denominators, IDs, as-of evidence.
B: real-data deterministic probability + ticket optimizer, proper missingness.
C: each agent's evidence/picks/tickets and actual meaningful dialogue; learning ledger.
D: official pre-off vs official result forward tests, ROI and probability calibration.
E: full vertical Japanese racecard + expert visuals + roundtable + final ticket table; independent print QA.
F: scheduled PRE lock, official result ingest, auto-settlement, alerts on missed locks; report coverage denominator.

## Next acceptance queue
P0: Add executable pre-race completeness validator and official payout settlement tests; integrate with the existing Phase B/Exchange API.
P0: Connect the validator to the daily automation, and make '0 completed forecasts' a visible critical failure.
P1: Implement per-agent tickets/pass and paper binding; capture actual as-of evidence.
P1: Verify official JRA/NAR race universe and produce one real pre-off lock.
P2: Produce a complete graded-race illustrated roundtable with licensed source visuals and print QA.
P2: Run first next-day verified forward settlement and postmortem; compare to the previous model.
P3: Expand to all races, then require repeated successful daily runs before PRODUCTION.

References: prism/README.md, docs/roadmap/PHASE_ABCDE_PARALLEL_20261018.md, GitHub PRs #3–#6, Notion master roadmap.
