# February research freeze — 2026-10-19

Freeze point: after the retrospective January comparison, before verified
February inputs or February evaluation results are available. This is a February
historical-control protocol, not a claim of January preregistration or forward
availability.

- Keep all four candidates: ability, +jockey, +body, +both. Do not select only a
  favorable January metric. Model hashes are recorded in FEATURE_MATCHED_20261019.
- Keep the fitted January 1–15 coefficients, scaling, missing indicators and
  optimizer settings. No fitting/tuning against February outcomes.
- Initialize ability/rider histories with the audited prior data through January
  31. Freeze predictions for every race in a calendar day before applying any
  result from that day. Do not use archived current rider aggregates.
- Apply the same source-scoped identities and feature transformations. Missing
  features stay missing; no zero substitution or performance-based race removal.
- Reconcile February race universe, duplicates, runner IDs, cancellations and
  payout completeness before scoring. Compare the same eligible cohort in every
  variant and publish coverage/exclusions before looking at variant rankings.
- Predict probabilities without result fields. Keep results in the evaluator.
  Unknown original availability remains HISTORICAL_RECONSTRUCTION_NOT_PIT.
- Report log loss, Brier, pooled-runner ECE, missingness, one 100-yen WIN ticket
  per race, refunds separately, effective return, profit and chronological MaxDD.
  Missing winning payouts stop monetary scoring until resolved.
- Publish paired daily-block intervals for probability and profit differences,
  with 1,000 resamples and seed 20261019. Disclose few-day uncertainty and that
  the intervals condition on fitted models.
- Keep January and February tables separate. No automatic production adoption.
  A later refit is a new candidate/version with a separate evaluation protocol.

Frozen aggregate:
`f317f7f638a45ce48c0568b85d31e6d5e1b69ed756e47d43db43090f6b41bcfc`.

| Candidate | Full model hash |
|---|---|
| Ability | `4bfb2a2e5e723f86726b065f961cab7a1bb869beb4734b2171d1daa019a30d13` |
| +Jockey | `2f6278d6e1cb5b06909edc6060e69a7a44284d3c28ec0da26e74c0c6e969699c` |
| +Body | `e8e91e8a5ff9abdb968e06994704915d7f2c79b6519c8765db3f2c29c510ceba` |
| +Both | `0bd162104cc0bd61dd8a7807e361bd0d3849c9790f580fcc5fabaa603c0f49b6` |

Execution status: NOT RUN; February inputs not yet verified. Any necessary
protocol change must be recorded before running the affected comparison.

