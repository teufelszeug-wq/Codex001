# PRISM operational policy — 2026-11-08

**Status:** Active decision. Supersedes former external-certification M4 as a mandatory milestone. Phase A–F remain the master roadmap; do not treat legacy M4 as an operational dependency.

## Priority and deadlines

1. **Before every racing day** establish the official JRA/NAR race universe, scheduled/updated post times, runners, scratches, and race identifiers. Prioritize JRA 11R at every racecourse, graded races, and significant NAR races in ascending off-time. Extend to other races after main-race coverage.
2. Produce and save **all-runner diagnoses**, independent editor/paper, Rio and registered expert-agent selections with reasons, named horses, explicit marks, and ticket choices or pass. Each ticket uses a **100-yen unit**. Do not substitute a role-played specialist conversation for genuinely independent model execution.
3. Finish **ordinary pre-race forecast history** before off. Store `race_id`, date/course/race/name, `scheduled_off`, `observed_off` when available, `saved_at_utc` and `saved_at_jst`, `source_refs`, input edition, forecaster IDs, all-runner analyses, selections, tickets, total stake, `forecast_version`, and optionally content hash.
4. Changes append new revisions while retaining originals and saved times. An edited or reconstructed post-off pick is **never** a pre-off performance record. If saved-time evidence is insufficient, label it `UNVERIFIED_PRE` or `RETROSPECTIVE` and exclude it from certified forward metrics.
5. Conduct at least five natural discussion topics per race where possible (all runners; course/track bias; condition/training; expert recommendation challenge; concrete 100-yen wagers), coordinated by editor 篠宮律, with rookie reporter りお as questioner and independent forecaster. Debates may continue after forecast save and **must never block** initial predictions.
6. Upon official results and dividends, reconcile actual runner/race IDs and handle scratched horses, refunds, ties, and cancellations, settle **100 yen per ticket** by editor/expert, then record forecast errors, counterarguments and time-respecting candidate learning decisions.
7. Publish the M-PAPER vertically laid out editorial paper from actual saved forecast records, with main races prominent. Keep predictions and retrospective commentary distinct.

## Success, failure and audit

- Report `official_main_races`, `all_runner_diagnosed`, `prerace_forecasts_saved`, `editor_and_expert_pick_coverage`, `five_topic_discussions`, `officially_settled`, race names/IDs, artifact URLs and missing reasons **from actual records**, not inferred completed work.
- **Zero pre-race forecasts for available main races is a CRITICAL operational failure**, regardless of code/CI/synthetic test success.
- No results leakage. Only truly saved forecast versions before the actual start count as forward records. Backtests must follow a chronological feature cutoff and disclose unknown provenance.

## Removed mandatory external milestone

Third-party RFC3161 TSA, cloud S3 Object Lock/WORM COMPLIANCE, proof-chain certification and the standalone former **M4** milestone are **not required** and must not prevent normal forecasting, settlements, discussion, paper or learning. They are optional future enhancements **only at user request**, not a scheduled goal. Preserve historical M4 code/docs/tests for reference; do not delete or claim certified production performance.

## Active implementation focus

- Official racecard collector and time/scratch reconciliation.
- Reliable daily scheduler with pre-off race deadlines, persistence, retry, and coverage alert.
- Actual full-field prediction and per-forecaster wager/passes; versioned history.
- Official settlement and learning loop; editorial and newspaper outputs.
- Tests must verify this operational flow with genuine documented data and distinguish it from synthetic-only scope.

Related: [Notion PRISM master roadmap](https://app.notion.com/p/3ed76efc40298187abd8fd105b2d5a76), [deferred certification issue #8](https://github.com/teufelszeug-wq/Codex001/issues/8).
