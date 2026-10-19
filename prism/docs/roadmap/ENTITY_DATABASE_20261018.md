# Horse / jockey profiles and discussion evaluation database

Implemented 2026-10-18 under Phase A/C. One relational SQLite database provides
separate horse and jockey profiles, rather than a disconnected physical database
for each individual. The real populated database is a private deliverable, **not
part of the public Git repository**. Code, synthetic tests and aggregate receipts
are public; original official raw files and individual recovered records are not.

## Structure

| Record | Contents and links |
|---|---|
| `horses` | Source-scoped identity, display name, canonical ID if proven, explicit provisional status |
| `jockeys` | Authority-scoped exact raw-name bucket, canonical ID if proven, explicit provisional status |
| `races` / `entries` | Race conditions, horse/frame numbers, horse–rider pairing and dated participation history |
| `observations` | Bodyweight/change, burden, recovered rider aggregates, pedigree/trainer and other available source details; source hash and availability class |
| `discussions` | Entire supplied transcript, evidence, speaker roles, input/prediction version, execution mode and separate PRE/POST records |
| `assessments` | Speaker, subject, claim, response, invalidation condition, evidence and version links; horse versus explicit jockey subject distinguished |

Result rank, final time, closing sectional, popularity and payout information
are not PRE model observations. Available recovered result fields live in an
explicit POST subsection of entry history. Missing fields stay unrecorded;
unknown publication times are not inferred from race dates.

## Initial actual import

- December bootstrap + January 2026: **2,952 races, 33,158 entries**.
- Horse records: **14,971 provisional source identities**; not 14,971 externally
  verified distinct horses. Matching composite identities can link across months;
  names alone never canonically merge identities or JRA/NAR populations.
- Jockey records: **416 authority-scoped exact-name buckets**; not licensed-ID
  verified distinct people. Cross-authority names and ambiguous spellings are not
  silently merged.
- **30,752 observations**: 15,376 quarantined metadata/body/rider observations and
  15,376 additional raw-detail snapshots. NAR details include available sire/dam/
  damsire, birthdate/colour, trainer/affiliation and career/course aggregates;
  JRA details include only the recovered fields actually present. Owner personal
  names are excluded from the new detail store.
- Actual discussions and assessments: **0**. The storage/validation interface is
  implemented and tested, but no simulated judgments are inserted into real history.
- Original timestamp/canonical-ID certification remains unresolved. Counts are
  import/recovery facts, not trained-model quality or PRE availability proof.

The machine receipt is
[`ENTITY_DATABASE_IMPORT_20261018.json`](../../artifacts/audits/ENTITY_DATABASE_IMPORT_20261018.json).
The final accepted file is `prism_entities_verified_20261018.sqlite`.
Independent read-only integrity, foreign-key, count and byte-hash checks are in
[`ENTITY_DATABASE_VERIFICATION_20261018.json`](../../artifacts/audits/ENTITY_DATABASE_VERIFICATION_20261018.json).
An earlier malformed candidate is retained but not accepted or distributed.
The exact failure cause is unresolved. Existing-file import replay is now
read-only and refuses malformed/unsupported databases rather than initializing
or writing them. The final rebuilt file passed separate-process reopen and
unchanged-byte replay checks.

## Adding discussion evaluations

Use `prism_records.discussion.save_discussion(store, context, records, horse_map,
jockey_map=None, review=None, jockey_subject_turn_ids=())` after the Phase C gate.

Every mapped horse/frame/rider must match an existing race entry. The complete
discussion and evidence remain linked to immutable input and prediction hashes.
`TEMPLATE` retains its source transcript but creates **zero assessment rows**.
`ROLE_SIMULATION` and claimed `INDEPENDENT_EXECUTION` remain attributed,
unverified opinions: independent execution and training achievement stay false.
The target jockey must be explicitly declared for direct rider assessments;
related horse opinions are not silently counted as rider-skill ratings.

### Continuity is not a fresh introduction every race

Maintain two distinct memories: the horse's factual source history and each
speaker's recorded judgments about that horse. Optional `records.selections`
stores `agent_id`, `horse_id`, `selection` (`TOP_PICK`, `CONTENDER`, `WATCH`,
`AVOID`) and a bound `FINAL` `turn_id`. It is not inferred from old prose. One
agent cannot declare multiple top picks in the same race.

A Rio line such as “I picked this horse last time, so I am cheering for it again”
requires a prior eligible Rio top-pick record for the same identity. A prior
entry in the horse database alone does not establish that Rio backed the horse.
`prism_records.memory.agent_horse_memory` retrieves this as-of context without
writing to the database. It separates prior entries, personal discussions,
explicit selections and top picks, and returns conservative familiarity flags.
The read-only query CLI accepts `--agent-id RIO --as-of <timezone-aware-time>`
with `--kind horse --id <exact-horse-id>`. No actual prior Rio endorsements are
claimed for the initial archive: its discussion and assessment rows remain zero.

`prepare_race_memory` preloads the relevant runners/riders and speaker histories
once before a roundtable. `run_phase_abcde.py --records-db <private-db>` uses this
read-only step and freezes `records_memory.json` into the release; subsequent
verification and conversation can reuse `--memory-file <frozen-memo>` without
querying a changing database. The entire DB is not copied into the dialogue.
The memo uses exact race/runner correspondence and carries its own hash/as-of
boundary. Prior-race identities inside this explicitly validated memory scope
are historical references, not mismatched current-race predictions.

`build_discussion_context(bundle, memory=memo)` includes the validated memo and
an evidence reference. It changes conversation context only, never the locked
prediction's scores or probabilities. Ending a conversation still requires a
supplied, validated transcript before `save_discussion` appends any opinions.
Preloading does not invent, execute or count a conversation.
Templates are not personal experience; simulated role history retains its mode
and is not proof of independent expert execution. Future records and the current
race's own selections cannot establish a prior preference. Missing records mean
“no recorded preference,” not a fabricated first meeting or a fabricated endorsement.

Remembering an earlier preference never forces the same current prediction.
Retain the prior reasons, counterarguments and error review, then reassess the
current field, workout and condition. This history is dialogue context, not an
unvalidated numerical ability bonus.

### Research once, then refresh the changes

| Information | Update policy |
|---|---|
| Identity, pedigree and birth information | Reuse sourced facts; recheck contradictions, corrections and unresolved identity |
| Entries, workout, condition, bodyweight, rider pairing and market | Collect newly published versions for each race; respect the prediction lock |
| Speaker opinions and results reviews | Append by race, speaker, time and prediction version; never rewrite an old pick |

Every observation retains its source/hash/availability class. Append a new
versioned observation rather than overwriting the old value. Stable facts are
not researched from scratch on every appearance, but cached facts are not
assumed eternally correct. If recency/source/version is inadequate, recheck the
specific gap. Current collection and historical PRE certification remain distinct.

PRE discussion and POST error review are separate records. A review records an
error for inspection; it does not change weights or promote a candidate into a
learned production model. Natural-language evidence relevance still requires review.

## Lookup and reproduction

```sh
python scripts/query_entity_database.py --db /path/to/prism_entities_verified_20261018.sqlite
python scripts/query_entity_database.py --db /path/to/prism_entities_verified_20261018.sqlite --kind horse --search 'name'
python scripts/query_entity_database.py --db /path/to/prism_entities_verified_20261018.sqlite --kind jockey --id 'returned-id'
python -m unittest discover -s tests/records -v
```

Lookup uses SQLite read-only mode. Horse profiles return participation history,
source observations and linked assessments. Jockey profiles separate direct
jockey judgments from related horse judgments. Returned historical profiles
contain POST/UNKNOWN records and must not be fed wholesale into PRE prediction.

`scripts/build_entity_database.py --help` documents the local import inputs.
Imports use foreign keys and a single transaction, validate recovered candidate
hashes against raw extraction, reject partial/changed inputs, and replay identical
content without changing the database. Code paths use fixed table names and
parameterized values. Existing immutable rows are never silently overwritten.
An import receipt is versioned by `RECEIPT_KEY`; changing the extraction contract
requires an explicit new version/migration, not silently reusing an old receipt
to claim newly added details.

## Next data work

Resolve official horse/rider IDs with a reviewed mapping ledger, acquire dated
workout/condition/rider evidence, and collect genuine pre-race specialist records.
Keep source rights, temporal uncertainty, authority and historical correction
versions attached. A populated archive is not a certified forward feature store.
