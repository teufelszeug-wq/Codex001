# PRISM operational pipeline — 2026-11-15

This track implements the approved preceding-day workflow. It preserves the six
phases, the experimental research engine and the existing immutable records.
Implementation and software/layout verification do not establish genuine forward
performance or production operation.

## Inputs and identity

- Export the current Notion character database to a private JSON source containing
  `records`, `source_url`, `captured_at`. Each record contains `agent_id`, `name`,
  `role`, `configuration`, `source_page_url`. `characters.py` freezes and verifies
  the snapshot. Unconfirmed settings stay unconfirmed; no fictional personalities
  are filled in. The checked source has 19 people; the older 20-person report
  remains an unresolved history difference, not a hard-coded roster size.
- A watch uses an official URL, expected date/venue/race number (and JRA race
  name), character source path, horse-evidence path and explicit engine course
  parameters. `prepare_watch` freezes the official bytes and validates identity.
  It cannot create horse performance evidence from an entry list.
- `prism.engine.raw/v2` distinguishes `ENTRIES_CONFIRMED` from `DRAW_CONFIRMED`.
  Thursday inputs may keep all draw numbers null. Predictions use horse IDs;
  gate-dependent bias is unavailable until the draw. Scratches never renumber
  the remaining gates. Existing v1 research inputs remain supported.
- Preserve raw official files and private records outside public Git. A local
  content hash verifies integrity, not original publication time or predictive
  accuracy. An official result with unknown publication time keeps null and
  records the first actual observation separately.

## Independent calls and preceding-day publication

Configure `OPENAI_API_KEY` and an explicit `PRISM_OPENAI_MODEL` in the execution
environment, never in source files. No model ID is guessed. For durable receipt
verification across API-key rotations, configure a separate random persistent
`PRISM_RECEIPT_SIGNING_KEY` in the private environment. Without it, the adapter
derives a signing key from the API key; changing that key affects past receipt
verification. This is a local signature, not a TSA or OpenAI attestation.

1. Acquire and normalize official entries immediately after confirmation.
2. Run the experimental core once and share the locked, versioned output.
3. Call each configured forecaster separately and durably save all-runner
   diagnoses, explicit marks and tickets or a reasoned pass. Initial calls do not
   see other forecasters' predictions. Before horse numbers exist, tickets stay
   empty with an explicit reason.
4. Editor 篠宮律 facilitates five distinct topics; りお asks and gives her own
   view. Every participant responds to the actual saved evidence and preceding
   turns. Editorial predictions are attributed to 本紙, with the canonical editor
   configuration retained as their source, not a newly invented persona.
5. Call each forecaster again with the complete discussion. Record changed or
   retained conclusions and their reasons. Retain API response IDs, complete
   request/response hashes and the actual durable-save receipt.
6. Generate all-page vertical HTML, PDF and PNG. Inspect every page, then record
   the visual QA using `confirm_visual_qa`. Mechanical execution alone leaves
   QA at EXECUTED. `publish` checks order, all participants/horses, tickets,
   source bindings, signed provider receipts and the actual PDF/PNG hashes.

The formal gate requires DRAW_CONFIRMED and publication before the race's JST
date. A generated preview or a late same-day run never becomes an accepted
preceding-day publication. Injected API transports are always SYNTHETIC. Merely
setting `independent_execution=true` or inventing an execution ID is insufficient.

## Commands and persistence

Install the optional Python runtime with `python -m pip install '.[operations]'`
from `prism/`; Chromium, Japanese Noto CJK fonts and Node are also required.
Run the CLI from the checkout so the Python and Node settlement code share the
same source version:

```sh
python prism/scripts/prism_operations.py --data /private/prism run --config /private/jobs.json
python prism/scripts/prism_operations.py --data /private/prism worker --config /private/jobs.json
python prism/scripts/prism_operations.py --data /private/prism status
python prism/scripts/prism_operations.py --data /private/prism publish --race-id RACE_ID --edition EDITION --qa-manifest /private/reviewed-paper.json
```

Configuration supports `jobs` with `race_id`, `card`, `characters`,
`engine_input`, optional `edition`, `due_at`, `render`; and `watches` with the
official-input fields above plus `engine_parameters` (`venue`, `surface`,
`distance_m`, `direction`, `class_rating`, `barrier_count`), optional `not_before`
and `render`. Use absolute private paths. The shipped empty example never claims
coverage of a racing day. Watches reuse unchanged source bytes and start a new
edition after draw/source changes; missing evidence remains BLOCKED.

SQLite records jobs and receipt times. Exclusive race locks prevent concurrent
workers; fsynced content-addressed artifacts are immutable. A restart reuses
successful calls and retries missing calls. Deadline crossings stop further
calls and preserve any response already received. Different inputs require a
new edition. Published editions are idempotent and cannot be replaced.

For automatic result polling, add `settlements` containing `race_id`, `edition`,
`authority`, `result_url`, `expected_date`, `expected_venue`, `expected_race_no`,
optional `expected_race_name` and `reflect`. Each worker tick waits for a saved
publication and off time, fetches the official result, settles and optionally
reflects. Missing results remain pending. Identical source/result retries do not
add performance; observed corrections append separately. A failed reflection
retains its completed computed settlement.

The `discover --authority JRA|NAR --date YYYY-MM-DD` command retains the official
navigation/calendar source and returns candidate URLs plus explicit gaps.
`DISCOVERED_LINKS_ONLY` is not a verified card, forecast or whole-day coverage
claim. Use the confirmed catalog to configure the private watch/evidence inputs.

The Dockerfile and Compose configuration provide a non-root worker, a persistent
volume and a loopback Reader port. Put deployment credentials in the untracked
`prism/deploy/.env`, configuration under its private `config/`, then build from
the repository root. In a managed proxy environment, pass the session's combined
CA bundle as BuildKit secret `system_ca`; do not bake it into the image. The
Reader presents edition archives, PDF links and official settlement performance.

## Race-day differences, results and learning

```sh
python prism/scripts/prism_operations.py --data /private/prism delta --race-id RACE_ID --base-edition EDITION --version day-v1 --input /private/delta.json
python prism/scripts/prism_operations.py --data /private/prism delta-paper --race-id RACE_ID --version day-v1
python prism/scripts/prism_operations.py --data /private/prism delta-publish --race-id RACE_ID --version day-v1 --qa-manifest /private/day-reviewed.json
python prism/scripts/prism_operations.py --data /private/prism collect --authority NAR --url OFFICIAL_RESULT_URL --date YYYY-MM-DD --venue VENUE_CODE --race-no NUMBER --result
python prism/scripts/prism_operations.py --data /private/prism settle --race-id RACE_ID --edition EDITION --result /private/result.json --reflect
```

`collect` returns `{record,artifact}`; save its `record` as the result input.
JRA also requires a matching official result URL and venue name. Race-day input
contains `changes`, `change_reason`, `source_snapshot`. Only weight/change,
odds, going, weather, track bias, scratches and rider changes are allowed.
The official raw snapshot must be retained and identity-verified. The original
core lock and preceding-day publication remain unchanged. Corrected AI outputs
and paper are separate editions; a result field cannot enter a PRE difference.

Settlement revalidates the saved publication, receipt signatures, source payload
and actual pre-race persistence before invoking the Node calculator. It handles
eight ticket types, 100-yen multiples, unordered pairs/triples, frame numbers,
ties, refunds, cancellation and official corrections. Unknown payout coverage
is pending, not a loss. Corrections and different forecast editions stay separate.

POST summaries and optional individual API reflections are retained separately.
An unavailable API cannot erase a completed computed settlement. Learning records
are CANDIDATE_SHADOW_REQUIRED and unadopted; saving a reflection is not training.
Historical local-rule or automatically edited dialogue from PR #12 is preserved
as its stated mode, never converted to independent model evidence.

## Verification and remaining release conditions

```sh
python prism/scripts/verify_operations.py --out /new/private/verification-directory
```

This runs all Python groups, the preceding-day gate and all Node suites, retaining
logs and explicit software-only counters. Root/package discovery can repeat
tests; report counts are suite executions, not unique assertions or learning
events. Browser and Node subprocess checks must actually run, not silently skip.

The November 15 report retains genuine source-acquisition evidence, synthetic
layout QA and software tests separately. Existing PR #12/Library reports of
149 race forecasts and 12 settlements have not been independently re-audited
here; they must not be described as zero, or counted as API/whole-flow acceptance.

Still required for release: configured API/model and persistent host, current
official identities and source-backed horse features, an actual JRA preceding-day
issue through next-day result reconciliation, equivalent NAR operation, scheduled
runtime observation and the existing Phase B/D model/forward acceptance. No TSA,
S3 Object Lock, or former M4 milestone is required.
