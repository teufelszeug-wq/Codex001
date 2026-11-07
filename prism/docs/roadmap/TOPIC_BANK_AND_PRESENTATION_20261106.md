# PRISM Topic Bank and illustrated roundtable — implementation contract v1

Status: prototype, not production. This extends Phase C/E/F and does not replace forecast-first acceptance.

## Requirements
- Unlimited Topic Bank; 1,000 is an initial waypoint, not a cap. Each race has five required independent themes, graded races may expand.
- Topic record: stable topic_id, category, hypothesis, scope, evidence requirements, origin agent, related race/horse, expected falsifier, duplicates, status, usage, and post-result evaluation.
- Deduplicate by normalized meaning (not just exact string); do not count paraphrases as new. Track candidate/adopt/merge/defer/retire and meaningful actual uses.
- Every participating specialist presents evidence, independent marks, own 100-yen tickets or explicit pass, then questions, rebuttals, minority positions and an editorial conclusion. Shinomiya Ritsu chairs; Rio interviews and presents her own selections.
- Visual evidence registry: chart definition/data, photo provenance/rights, video URL and timecode, observed/available timestamps. Unseen visuals must not be described as inspected.
- Print: vertical Japanese text throughout, racecard → editorial → comparative visual evidence → late roundtable. Video appears as documented frames/QR or reference, not embedded print media.
- Metrics: actual distinct topic IDs used, actual utterance characters, questions/rebuttals, agent coverage, final tickets, print QA, and after-result prediction improvement. Counts cannot replace pre-off lock.

## Implementation sequence
C1 Topic schema, category taxonomy and deterministic exact/near duplicate candidate triage.
C2 Topic selection from horse DB, race features, uncertainty and agent disagreements; budget and novelty rules.
C3 Real independent agent execution, blinded first round, presentation, cross-examination, final tickets.
C4 Learning ledger, per-topic outcome validation, minority truth and retention/retirement.
E1 Evidence visualization registry and media rights/availability checks.
E2 Vertical layout and full-length newspaper transcript with editorial condensation separately labeled.
E3 PDF/PNG print QA, text overflow, glyph orientation, source captions and media references.
F1 Scheduled task reads Topic Bank and outputs topic/agent/evidence completeness gate.
F2 Production integration, persistent replay, official race forward validation and continuous monitoring.

## Acceptance
Prototype functions and synthetic tests are not proof of independent AI calls, topic originality at scale, production print QA, or real prediction accuracy. These require separate verifiable artifacts.
