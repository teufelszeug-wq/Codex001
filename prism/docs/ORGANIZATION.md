# Repository organization

Scope is `prism/` only. Keep the repository's other projects and open PRs intact.
Do not rename the repository, rewrite history, remove branches, or change public
visibility as part of this task. The root GDA-only README mismatch is recorded,
but its cross-project correction requires a separate scoped change.

| Location | Responsibility |
|---|---|
| README.md | Master six-phase roadmap and navigation |
| docs/ | Requirements, decisions, status, module limitations |
| src/prism_mdisc/ | Imported discussion structural-audit module |
| tests/ | Synthetic checks only; not training or racing records |
| scripts/ | Reproducible local verification entrypoints |
| manifests/ | Asset identity, source hashes, recovery and migration status |
| reports/ | M-DISC synthetic verification evidence; foundation evidence remains under artifacts/audits/ |

Keep existing schemas and docs/canon authoritative; avoid empty placeholder
directories and parallel competing plans. B0–B11, VAL, and paper IDs remain
subordinate tracks. Prefer checklist acceptance criteria over new milestone IDs.

GitHub is the code/schema/test/audit source of truth. Notion is the roadmap and
decision mirror; legacy saved files are migration sources. No Notion update is
claimed by this PR. Cross-chat sync remains pending until its actual update.

## Publication controls

This is a public repository. Publish only reviewed project-authored source,
synthetic fixtures, non-sensitive metadata and sanitized reports. Do not commit
credentials, private chat exports, signed URLs, full licensed race feeds or
third-party newspaper/video material. Record provenance/rights before adding data.

## Review and rollback

Use a dedicated branch and PR. Verify the patch touches only `prism/`; run
`python3 scripts/verify.py` inside that directory. Preserve old artifact hashes.
Review before merging. Before merge, rollback means closing the PR without
changing main; after merge, prefer a normal revert commit over history rewriting.
