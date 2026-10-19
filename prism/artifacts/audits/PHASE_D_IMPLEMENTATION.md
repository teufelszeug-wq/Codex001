# Phase D — archived research comparison

## Completed scope

January 2026 archived ordinal, next-day sensitivity, and B0 baseline were matched on
all 1,354 race IDs and runner sets. Their archived predictions and evaluation hashes
were bound, prediction content hashes and archived event-chain/review hashes verified,
B0 event-chain/evaluation hashes checked, and standalone expert reads revalidated,
outcomes cross-checked, and LL/Brier recomputed from probabilities rather
than copied from summaries. This is a descriptive comparison of existing historical
research, not validation of the new full-feature Phase B engine.

| Run | LL | Brier | Net profit | Refund-excluded return | Maximum drawdown |
|---|---:|---:|---:|---:|---:|
| Archived ordinal | 2.134484 | 0.844931 | -48,880 yen | 63.5768% | 49,100 yen |
| Archived next-day | 2.135599 | 0.845130 | -48,200 yen | 64.0835% | 48,420 yen |
| B0 baseline | 2.213588 | 0.863998 | -45,910 yen | 65.7899% | 45,990 yen |

Every ticket is 100 yen. Legacy `payout_yen` includes refunds; the adapter subtracts
refunds once before comparison. Return = payout excluding refunds / (purchase -
refunds). Max drawdown uses the same date/time/race-ID order for all methods; ties
at the same time use lexical race-ID order, not a claimed actual payment sequence.
Calibration bins pool runner probabilities with fractional dead-heat targets.

B0 had a smaller observed monetary loss but larger probability errors. Neither
observation establishes prospective or causal superiority. The comparison is not
a controlled isolated-feature experiment: the old mixture and B0 differ in several
ways. Expert-only probabilities are reported separately; no new expert ticket
payouts were inferred from incomplete payout information.

## Chronological calibration experiment

The B0 baseline temperature was fitted to January 1–15 (653 races) using only that
subset and a fixed seven-value grid. T=1.5 was selected. January 16–31 (701 races)
was evaluated without refitting: LL 2.182309 → 2.127328; Brier 0.859783 → 0.846409.
The frozen parameter is a proposed February research rule, not a production change.
The split was specified retrospectively, not preregistered in January. The held-out
results were not used to choose the temperature. February data was not used.

## Remaining limitations

- Strict point-in-time certification: **0/1,354**.
- February evaluation: **not performed**.
- New Phase B full-feature real-race validation: **not performed**.
- Original external result-source authenticity was not independently recertified.
- These reports contain aggregate metrics and hashes only; raw horses/results stay local.
- Phase D as a whole remains **incomplete**.

## Reproduction and integration

Run `python scripts/compare_january_research.py --archive-root <replay_202601>
--b0 <b0_run1> --out artifacts/audits/PHASE_D_JANUARY_COMPARISON.json --experiments`.
Reruns require byte-identical existing output; differing overwrite is rejected.

Run `python -m unittest discover -s tests/validation -p 'test_*.py' -v`.
17 unit tests passed, covering dead heats, refunds, drawdown, matched cohorts,
outcome mismatch, content/event tampering, determinism, and holdout-label independence
of the frozen parameter. Hash integrity does not establish historical availability.

`prism_validation.compare.compare_runs(runs, scope='SYNTHETIC_COMPARISON')` accepts
a mapping from method name to canonical rows. Each row contains `race_id`,
`order_key`, `probabilities`, `winners`, `stake_yen`,
`payout_excluding_refund_yen`, `refund_yen`, and `prediction_hash`; `pick` is optional.
The report schema is `prism.validation.comparison/v1`. A synthetic integration report
must retain its synthetic scope and cannot be presented as January evidence.

The January report intentionally has no binding to a new Phase B prediction hash:
renderers must label it as an independent historical aggregate, not as evidence for
the current race's predictive performance.
