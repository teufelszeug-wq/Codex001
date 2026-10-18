# PRISM Roundtable M-T4/T5/T6 (2026-10-18)
A standalone, standard-library acceptance gate for racing roundtables.
The full local prototype includes the Tokyo 1R official-roster fixture, source ledger, dialogues, scoring firewall, and 34 unit tests; this branch initially carries the portable acceptance script and status.

## Workflow
1. Verify race header against official runner manifest and start time.
2. Editor introduces the race and course BEFORE the first horse.
3. Run all horses in ascending number. Each horse needs a named core assessment.
4. Let りお ask follow-up questions, experts disagree, editor recap the dispute.
5. Run: python prism/roundtable_tseries/verify.py meeting.json
6. Mark single-model character simulations distinctly from independent expert execution.

## Local results
- JRA Tokyo 1R on October 18, 2026: 12 of 12 named horses, 19 speaker roles, 90 turns, 4,635 spoken characters in B-01.
- Four dialogue variant configurations use the SAME retrospective fixture (B-01, A-02, A-03, A-11).
- Twelve scenario prerequisite gates are unit-tested with synthetic inputs.
- 34 local tests passed. Verified forward prediction score samples: 0.
- Full data retrieval dates are later than race start; do not call these verified pre-race forecasts.

## Source references
- JRA official racecard: https://www.jra.go.jp/JRADB/accessD.html?CNAME=pw01dde0105202604070120261018/00
- JRA Tokyo course: https://www.jra.go.jp/facilities/race/tokyo/course/index.html

## Remaining acceptance gates
- Each of 11 specialized variants needs its own appropriate, source-vetted real race.
- Human dialogue quality assessment not performed.
- No independently executed specialist models.
- No externally attested pre-race snapshot; no genuine Brier/ROI result.
- A passing structural test alone cannot close all milestones.
