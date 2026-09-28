# Creative Consistency OS

A local-first creative production system for long-form fiction: World Builder + Language/Culture + Story Bible + Writing Room + Entity Intelligence + Core Lint + Change Impact + genre-specific verification.

## Current progress

- M0 Foundation — complete
- M1 Application Foundation — complete
- M2 World Builder Alpha — complete
- M2.5 Language & Culture Builder — complete
- M3 Story Bible + Writing Room — complete
- M3.5 Entity Intelligence — complete
- M4 Core Lint Engine — complete
- M4.5 Change Impact Engine — complete
- M5 Isekai Pack — complete
- M6 LN Genre Packs — next

## Current Golden Path

Genre → Setup Mode → World DNA → Language/Culture → Story Bible → Writing Room → Entity Intelligence → Consistency Lint → Change Impact → Genre Pack Verification

The system now supports structured world-building, fictional-language/culture design, author-controlled Canon states, chapter writing with revision history, timeline, aliases, manuscript mentions, ambiguity-aware entity resolution, relationship graphs, evidence-backed consistency diagnostics, dependency-aware selective revalidation and an opt-in Isekai verification pack.

Author-control rule: generated, extracted or inferred material never becomes CANON automatically. Lint, Change Impact and genre packs never auto-rewrite prose or Canon.

## Current schema

Project schema version: 8

Migrations:
- 0001 M1 baseline
- 0002 World Builder Alpha
- 0003 Language & Culture Builder
- 0004 Story Bible + Writing Room
- 0005 Entity Intelligence
- 0006 Core Lint Engine
- 0007 Change Impact Engine
- 0008 Isekai Pack

## M4 Core Lint

Core Lint provides:
- configurable rule enable/disable
- HINT / INFO / WARNING / ERROR severity
- document and project lint runs
- missing/stale Entity Mention checks
- mention-span integrity
- unresolved/ambiguous references
- Canon-state reference diagnostics
- normalized name/alias collisions
- timeline/relation Canon consistency
- lexical name-drift hints
- custom project term constraints
- evidence/fingerprint persistence
- finding triage

## M4.5 Change Impact

Change Impact provides:
- rebuildable dependency graph
- Bible → Alias / Mention / Manuscript / Timeline / Relation connections
- normalized direct surface-reference fallback
- bounded transitive impact preview
- automatic invalidation queue
- selective re-lint of affected manuscripts
- author dismissal

## M5 Isekai Pack

M5 provides:
- opt-in Earth-Origin Guard
- configurable strictness and categories
- allowlists and custom terms
- author-approved World-Origin Mapping
- optional source-place provenance
- travel-time rules
- magic-cost rules
- currency and price-band checks
- healing-limit rules
- M4 Findings rather than a separate warning system
- M4.5 global policy invalidation
- source-place → replacement → manuscript impact propagation
- Isekai Guard web workspace

See docs/M5.md for the data contracts and author-control rules.

## Structure

- apps/web — Next.js + TypeScript
- apps/api — FastAPI + SQLAlchemy + Alembic
- docs/M1.md
- docs/M2.md
- docs/M2.5.md
- docs/M3.md
- docs/M3.5.md
- docs/M4.md
- docs/M4.5.md
- docs/M5.md
- docs/ROADMAP.md

## Validation

Current M5 validation:
- 32 API tests passed
- Alembic upgrade succeeded through 0008
- Next.js production build succeeded

## API local development

cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --port 8000

Windows activation: .venv\\Scripts\\activate

## Web local development

cd apps/web
npm install
npm run dev

Default API URL: http://localhost:8000
