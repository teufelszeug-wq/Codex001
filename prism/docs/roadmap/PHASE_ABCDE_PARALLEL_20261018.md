# Phase A–E parallel implementation and coordinated acceptance

Started: 2026-10-18; final integration verified 2026-10-19 (Asia/Tokyo).
Base: main after PR #3. PR #4 is a separate,
preserved draft. This is one integration batch under the existing six phases,
not a new major milestone or a declaration that A–E products are finished.

## User-approved execution plan

1. Make Phase B practical: bridge experimental formulas to usable specialist/
   N-Value, workout, condition and jockey models, with explicit missingness.
2. Compare Phase D on the same January races: ability-only and additional
   components, probability error, feature missingness, returns and drawdown.
3. Audit and integrate dialogue: editor/facilitator 篠宮律; りお asks and deepens
   questions, receives specialist responses and gives a final view. All horses,
   evidence, counterarguments, minority views and natural dialogue must remain.
4. Freeze rules before February, validate untouched control data, connect the
   accepted output to vertical publishing, and only then automate operation.

Parallel work does not remove these acceptance dependencies. A/C/E may implement
and test contracts now; empirical release waits for B/D and editorial evidence.

## Implemented interfaces

| Phase | Interface | Verified boundary |
|---|---|---|
| A | `prism_exchange.build_manifest`, `verify_manifest`, `artifact_cache_key` | Shared race/input/prediction hashes, raw/racecard identity, dependency hashes, result separation, settlement arithmetic |
| B | Existing `predict`, `post_market`; ablation metadata; recovery census | 11-component removal diagnostics; non-floored positive calibration tails; market opening time retained |
| C | `build_discussion_context`, `validate_discussion`, `review_learning` | Full specialist × horse initial/response/final coverage, evidence/time links, Rio question/answer/final, POST-only review |
| D | `prism_validation.compare`, `scripts/compare_january_research.py` | Matched cohorts, monetary definitions, calibration/error controls and frozen research candidate |
| E | `prism_paper.render_paper` | Escaped four-page vertical HTML, all-horse frame/horse separation, fixed-100 candidates and separate comparison scope |

`scripts/run_phase_abcde.py` binds A/B/C/E for one race. Optional supplied
discussion must pass before publication. An absent discussion remains
`NOT_EXECUTED`, not a generated meeting. POST settlement and review do not
change PRE publication/cache entries. Saved mutable releases are rechecked
against manifest, file hashes, allowed filenames and deterministic rendering.
Optional `--records-db` preloads a race's relevant records once, freezing a
hash-bound as-of conversation memo. `--memory-file` reuses that memo. Current
race opinions, future records, templates and unknown-time result payloads do
not become prior experience or PRE factual evidence. This is continuity context,
not an ability-score bonus or a completed independent specialist execution.
D's multi-race research remains a separate aggregate; it is not smuggled into
a single race's PRE evidence or claimed as the new engine's performance.

## Actual January findings

All three recorded runs cover the same 1,354 races. Refunds are excluded from
both payout and effective stake for the primary return ratio.

| Research run | Log Loss ↓ | Brier ↓ | Effective return | Net profit |
|---|---:|---:|---:|---:|
| Archived ordinal integration | 2.13448 | 0.84493 | 63.58% | −48,880 yen |
| Archived next-day sensitivity | 2.13560 | 0.84513 | 64.08% | −48,200 yen |
| Reconstructed ability-only B0 | 2.21359 | 0.86400 | 65.79% | −45,910 yen |

B0 has a less-negative betting result but worse probability error. This does
not establish superiority or positive expected return. Max drawdown, reliability
bins, paired differences and coverage hashes are in the machine report.
Old expert controls (ability/course, career aggregate, uniform) are compared
for probability error only, not invented betting-policy returns.

Chronological calibration experiment: select a temperature using January 1–15
(653 races) only; evaluate once on January 16–31 (701 races). Selected T=1.5.
Holdout Log Loss changes 2.182309 → 2.127328, Brier 0.859783 → 0.846409.
This retrospective research split was not pre-registered in January. It is a
frozen **candidate** for untouched February evaluation, not production adoption
or certified forward evidence. Betting policy is unchanged.

## Raw feature recovery versus usable PRE features

The recovered normalized corpus and original raw files must be counted
separately. Jockey/bodyweight observations exist in raw sources but were dropped
by the earlier canonical parser. Current-race final time, rank, closing sectional
and payouts are POST-only. Unknown original publication times stay unknown;
recovery is not proof of PRE availability. The readiness census records exact
counts, source hashes, adapter gaps and temporal limitations. Do not replace
these gaps with zero-valued pretend ablations.

The allowlisted recovered-observation extractor was executed on all 15,376
January runners into a local quarantine store: frame, carried weight and jockey
name 15,376 each; bodyweight 15,273; bodyweight change 14,746; unverified jockey
aggregates 11,394. Canonical horse identity and original availability remain
unresolved for all rows, so engine-ready/PRE-certified/trained-model counts are
zero. Current-race outcomes are not copied into these observation records.
The public repository contains only code, synthetic tests and aggregate counts.
Raw-source census/extraction needs the `research` optional dependency (`lxml`).

## PR #4 read-only audit

The draft changed during this parallel batch. Reinspection at head
`4064a2006973a5ad3569f5a8ac7ab91293c818f9` found three files and five new regression
checks: Rio question marks, a counterargument tag, nonempty evidence/past facts,
and partial comparison/closing order. Earlier claims that these checks were
absent are superseded. These are still narrow structural checks, not semantic
evidence, full all-agent participation, natural cross-speaker responses, role
correctness or independent AI execution. Comparison may start before all horse
introductions finish, CLOSE need not be the final event, and nonempty evidence
is not a validated reference/hash/time. A Rio question need not be answered and
Shinomiya facilitation is not enforced there. The contiguous horse-number
assumption also mishandles scratches. No counts from that draft or these
synthetic fixtures are added to meeting/training achievements. The new C bridge
does not replace PR #4's presentation-order track or resolve editorial quality
automatically. PR #4 is preserved, not merged by this integration.

Reinspection on 2026-10-19 at head
`870fdba6bb80e9b410f400b4ac70c9508a28d38e` found a new `entry_manifest` route that
supports number gaps, explicit scratches/exclusions, source references and
retrospective time classification. All 11 portable GitHub tests were executed
successfully in an isolated directory. This supersedes the blanket scratch-gap
limitation above for the new route; the older verifier remains a separate path.
The draft also records larger local bundles and retrospective Tokyo fixtures.
Those packaged-only tests/transcripts were not rerun here or imported as verified
independent dialogue. Human naturalness, actual expert execution, strict forward
evidence and full code migration remain acceptance work.

## Reproduction

From `prism/`:

```sh
python -m pip install -e '.[research]'
python scripts/verify_cross_phase.py --out /path/to/new-audit-directory
python scripts/verify.py
python -m unittest discover -s tests/recovery -v
node tests/foundation/pipeline.test.mjs
```

The cross-phase report records separate suite executions; legacy recovery
checks overlap engine regression checks. They are not learning iterations or
real race evidence. The demo is synthetic and byte-reproducible. Raw official
corpora remain outside the public repository; publish code, aggregates and hashes.

Final synthetic/structural suite executions: engine 106, exchange 30, dialogue 30,
validation 17, readiness 13, paper 17, integration 13, records 75: **301 PASS**.
Independent builds produce byte-identical release artifacts. Separate legacy
checks also passed: M-DISC 15 unittest +
five direct checks, recovery 12 (eight overlap earlier engine recovery checks),
foundation seven assertions. Do not sum overlapping groups as unique achievements.

Additional user request: source-linked horse/jockey profiles and discussion
evaluations are implemented in `prism_records`, with read-only lookup and an
actual December/January private import. See
[the entity database record](ENTITY_DATABASE_20261018.md). Simulated assessments
are not inserted into the real database.

## Remaining completion gates

- B: repair/reconcile raw adapters and identities, recover actual historical
  workload/condition/jockey evidence, estimate/freeze models on separated data,
  then replay all available components. Experimental fixed coefficients and a
  hold-store observation adapter are not trained specialist models.
- D: full new-engine same-universe ablations with non-fabricated coverage;
  untouched February control, daily/block uncertainty and genuine future locks.
  Strict historical PIT remains 0/1,354; February is not verified.
- C: execute independent evidence-linked specialists and conduct semantic/natural
  dialogue review; trace candidate → shadow → adopt/reject without auto-adoption.
- E: actual editorial content, full-length variable-card stress tests and visual
  print QA. Chromium is unavailable here, so this batch has no visual QA approval.
- A/F: keep source rights/timestamps and identity debt explicit; no production
  scheduler, betting execution or release approval is added.
