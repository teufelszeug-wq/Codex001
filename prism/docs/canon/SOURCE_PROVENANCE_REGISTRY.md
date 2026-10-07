# PRISM Source & Provenance Registry v0.1

Status: IMPLEMENTED (registry contract)

| source_id | authority | role | temporal use | current note |
|---|---|---|---|---|
| JRA_OFFICIAL_RESULTS | JRA | official results / race facts | POST; some race facts usable only with proven pre timestamp | JRA publishes searchable historical results; 2002+ also has race-result PDFs |
| JRA_OFFICIAL_PROGRAM | JRA | planned universe / conditions | PRE | planned schedule must not be treated as Actual Universe without mutation crosscheck |
| NAR_OFFICIAL_DOWNLOAD | NAR | race list / official race data | PRE/POST by field and timestamp | official CSV download format documented; race list includes course/distance/weather/going/field size and sectionals |
| NAR_OFFICIAL_SCHEDULE | NAR | planned/actual meeting discovery | PRE | official site warns schedules can change |
| LEGACY_LIBRARY | ChatGPT Library | migration evidence | RESEARCH_ONLY unless original source/timestamp proven | never upgrades UNKNOWN_TIMESTAMP by itself |

## Required provenance fields
- source_id
- source_type
- source_uri or source_locator
- authority
- observed_at
- available_at
- retrieved_at
- race_id
- horse_id when applicable
- evidence_type
- pre_post_class
- confidence
- content_hash
- schema_version
- rights_class

## Rights classes
OFFICIAL_PUBLIC_REFERENCE / LICENSED / USER_PROVIDED / INTERNAL_DERIVED / UNKNOWN_RIGHTS.

UNKNOWN_RIGHTS data may be indexed for migration but must not be republished or committed as raw data to the public repository.

## Result firewall
Result-derived fields must never enter a pre-race feature artifact. A result exposure event sets MODEL_RESULT_EXPOSED and prevents later claims of genuine blind validation for affected historical predictions.
