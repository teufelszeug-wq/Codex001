# PRISM AI Registry v0.1

Current registry for Phase A governance.

- RIO-REPORTER-01: りお — rookie reporter / reader proxy — CANON
- RIO-DATA-01: 黒川 統司 — data analysis — CURRENT_NAME_RECORDED (旧名: 黒川 数馬; 「馬」の重複回避による改名。旧名復活禁止; 詳細人格は要照合)
- RIO-VIDEO-01: 三崎 レイ — race video — LEGACY_CANON
- RIO-REPORT-01: 牧野 俊介 — public stable/comment information — LEGACY_CANON
- RIO-BLOOD-01: 白峰 遥 — pedigree — LEGACY_CANON
- RIO-JOCKEY-01: 桐生 駿 — jockey — LEGACY_CANON
- RIO-ABILITY-01: legacy ability persona — RENAME_REQUIRED
- RIO-COURSE-01: 宮坂 直矩 — course — LEGACY_CANON
- RIO-BIAS-01: 橘 潮 — track bias — LEGACY_CANON
- RIO-PACE-01: 早瀬 展 — pace — RENAME_REVIEW (「早」「瀬」の字面重複が理由。改名後の確定名は未発見、推測禁止)
- RIO-VALUE-01: 穴見 爆 — value/longshot — LEGACY_CANON
- PRISM-NVALUE-01: N-Value — ability review and market value research — CANON
- PRISM-WORKOUT-01: 鷹取 美冬 — workout — CANDIDATE_ACCEPTED
- PRISM-EDITOR-01: 篠宮 律 — editor-in-chief, chair and final summary — CANON (later confirmed; supersedes historical NAME_UNRESOLVED)
- PRISM-QA-01: QA AI — audit — FUNCTION_CANON
- PRISM-STATE-01: State/Recency/Rotation — NAME_UNRESOLVED_IN_OLD_REGISTRY (later Notion has a candidate; verify before canonicalizing)

Rules:
- りお is not Editor-in-Chief.
- Renamed/retired identities are not silently resurrected.
- Duplicate names/readings are checked before a new persona name becomes canon.
- Unresolved persona names stay unresolved rather than being invented.

## Cross-system synchronization contract (2026-11-10)

- Canonical persona identity is the stable `persona_id`, never a display name. Preserve historical names as `aliases` with reason and superseded date; do not promote legacy names.
- For every approved name, role, personality, or visual change, prepare one change record with `change_id`, `persona_id`, `old_value`, `new_value`, `approval_status`, `source`, `notion_page`, `github_commit_or_pr`, `synced_at`, and `verification_status`.
- Update the GitHub registry on a feature branch and the matching Notion character page as one *tracked operation*. Verify both by re-reading. Because GitHub and Notion do not support a shared atomic transaction, mark `PARTIAL_SYNC` if either side fails; never report completion or silently continue using mismatched names.
- A PR is `PENDING_REVIEW` until merged; a Notion page must not claim that unmerged changes are already canonical on `main`. Track the PR URL and reconcile after merge.
- On startup or before generating dialogue/newspapers, compare `persona_id`, names, role, and version. If mismatched, fail closed for affected personas and open a reconciliation task. Never fabricate missing fields.
- Specific 2026-11-09 corrections: 黒川 数馬 is a retired alias replaced by 黒川 統司 to avoid repeated 「馬」; 早瀬 展 is under rename review due to repeated 「早」「瀬」; りお is always rookie reporter, not editor-in-chief; 篠宮 律 is editor-in-chief.
