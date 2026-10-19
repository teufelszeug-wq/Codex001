# A–E parallel integration — 2026-10-19

This batch advances the user's B → matched D → C → February/E plan.
It does not close the full five-phase product gate. Base: main
`fda857f7d7917d390c58a61702866a0ae7f36330` (PR #5).

| Phase | Implemented and checked | Remaining acceptance |
|---|---|---|
| A | Append-only horse/rider fact versions; cache hits; differences/corrections; source conflicts held; read-only as-of selection; one ledger prefetch shared by all AI memories | Authentic sources/timestamps and official identity resolution |
| B | Fitted L2 multinomial residual model with ability log-probability offset, train-only scaling, missing masks, frozen artifact hashes | Specialist/N-Value/workout/condition models; practical adoption |
| C | Immutable legacy-dialogue staging; original bytes/hash/receipt and exact entry bindings; explicit FINAL selections only | Actual sourced historical meetings and natural multi-AI conversation review |
| D | 653 training / 701 common holdout races, four feature variants, probability/missingness/100-yen settlement/drawdown and paired daily bootstrap | February controls, full B0–B11 comparison, forward evidence |
| E | Bound names/horse numbers/frame numbers; real 14-runner research output and 701-race comparison in four vertical pages | Visual/print/stress QA; actual accepted discussions |

## Real-data comparison

Training: January 1–15 (653 races). Evaluation: January 16–31 (701).
All variants use the same ability baseline with prior-day-only history, including
December bootstrap. The full day's predictions precede that day's history update.
Coefficients are frozen after training; holdout history updates are allowed after each day.
This differs from earlier B0's same-start-time batch update policy.

| Variant | Log loss ↓ | Brier ↓ | Pooled-runner ECE ↓ | Return rate | Profit (yen) | Max drawdown (yen) |
|---|---:|---:|---:|---:|---:|---:|
| Ability | 2.182309 | 0.859783 | 0.021279 | 58.77% | -28,740 | 28,810 |
| + Jockey | 2.138092 | 0.850595 | 0.022805 | 84.08% | -11,110 | 19,740 |
| + Body | 2.178261 | 0.860894 | 0.021048 | 70.70% | -20,390 | 21,690 |
| + Both | 2.135385 | 0.851339 | 0.022132 | 87.39% | -8,790 | 18,010 |

Each race places one hypothetical 100-yen WIN ticket on its highest probability
runner. Return rate is payout excluding refunds / effective stake; profit is
payout + refund − gross stake. Gross stake is 70,100 yen in each group.
Refunds are respectively 400 / 300 / 500 / 400 yen. Missing winner payouts fail
rather than silently becoming zero.

Jockey features use earlier January days only, with shrinkage and explicit cold
starts; unverified archived rider aggregates are excluded. Body weight and change
are reconstructed observations. Holdout missing rates: jockey 0.879%, weight
0.791%, weight change 4.270%.

Paired 16-day block bootstrap (1,000 draws) yields log-loss delta intervals:
jockey [-0.06149, -0.02913], body [-0.01090, +0.00186], both
[-0.06493, -0.03214]. These intervals condition on the fitted model; they do not
refit training data. Body alone has worse Brier and its log-loss interval crosses
zero. Both has the best log loss/return, while jockey has the best Brier. ECE
does not uniformly improve. All variants lose money.

This split was selected retrospectively. Historical publication-time certification
remains zero. Provisional rider identities, absent December rider history, and
unknown historical availability prevent adoption/forward claims.
Aggregate source: [FEATURE_MATCHED_20261019.json](../../artifacts/audits/FEATURE_MATCHED_20261019.json)
(hash `f317f7f638a45ce48c0568b85d31e6d5e1b69ed756e47d43db43090f6b41bcfc`).

## Continuity without invented memories

Source updates retain old versions, select the as-of version and hold conflicting
sources. Conversation prefetch reads the fact ledger once and reuses the same
selection for all agents. Managed retired/future versions do not become factual
evidence pointers. Unknown-time observations are not promoted to PRE.

The legacy importer stores original JSON, receipt time and exact horse/entry
bindings in a separate immutable ledger. It never manufactures PRE assessments
or infers TOP_PICK from prose. Its attributed-history reader is separate from
certified PRE evidence. Templates/unknown execution modes are excluded.

Actual eligible history import this batch: **0**. Inspected legacy packages
contained generators/policies rather than recorded meetings. Library
`run_t22_full_dialogue.py` explicitly describes an editorial prototype and
hard-codes dialogue; its input meeting document was not supplied.
`PRISM_座談会デモ_v0.9.10.html` contains fictional demo horses. Neither establishes
Rio's real-horse prior picks or independent AI executions. The accepted private
DB remains unchanged with zero discussion/assessment rows.

## Paper and next gate

A private research-only four-page HTML covers one January 16 Oi race, all 14
runners, names/frame/horse numbers/probabilities, fixed-100-yen comparison rules
and the four-variant aggregate. No dialogue is invented. The supplied historical
names/output are outside public Git. Structural checks pass; browser/print visual
QA has not run because no browser executable is installed.

[February protocol](../decisions/FEBRUARY_RESEARCH_FREEZE_20261019.md) freezes
the existing four candidates and comparison rules before new February data is
evaluated. No February input dataset was verified in this batch. Acquire and
audit February inputs, run the fixed controls, then decide adoption. Full
specialist/workout/state models and accepted natural dialogue remain separate work.

## Reproduction

```sh
python scripts/run_feature_experiment.py --january /path/january.json --bootstrap /path/bootstrap.json --database /path/verified.sqlite --out /new/FEATURE_MATCHED.json --models-out /private/models.json
python scripts/verify_cross_phase.py --out /new/acceptance --run-date 20261019 --base-commit fda857f7d7917d390c58a61702866a0ae7f36330
```

The first command reads the source DB through a read-only URI. Full models contain
training race IDs and stay private; the public aggregate publishes count/hash
instead. The second runs scoped suite executions, not learning events or
independent meetings. The machine report separately marks product, PIT and
production gates incomplete.

