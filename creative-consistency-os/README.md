# Creative Consistency OS

A local-first creative production system for long-form fiction: World Builder + Language/Culture + Story Bible + Writing Room + Entity Intelligence + Core Lint + Change Impact + modular genre verification.

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
- M6 LN Genre Packs — complete
- M7 Mystery / SF Verification — next

## Current Golden Path

Genre → Setup Mode → World DNA → Language/Culture → Story Bible → Writing Room → Entity Intelligence → Consistency Lint → Change Impact → Genre Pack Verification

The system supports structured world-building, fictional-language/culture design, author-controlled Canon states, revisioned manuscript writing, timeline, aliases, entity resolution, relationship graphs, evidence-backed consistency diagnostics, dependency-aware revalidation, Isekai verification and modular LN social/relationship verification.

Author-control rule: generated, extracted or inferred material never becomes CANON automatically. Lint, Change Impact and genre packs never auto-rewrite prose or Canon.

There is no mandatory primary genre. Genre packs can be disabled, enabled independently or combined.

## Current schema

Project schema version: 9

Migrations:
- 0001 M1 baseline
- 0002 World Builder Alpha
- 0003 Language & Culture Builder
- 0004 Story Bible + Writing Room
- 0005 Entity Intelligence
- 0006 Core Lint Engine
- 0007 Change Impact Engine
- 0008 Isekai Pack
- 0009 LN Genre Packs

## M4 Core Lint

Core Lint provides:
- configurable rule enable/disable
- HINT / INFO / WARNING / ERROR severity
- document, project and structural lint scopes
- evidence/fingerprint persistence
- finding triage
- extension contract for genre packs

## M4.5 Change Impact

Change Impact provides:
- rebuildable dependency graph
- transitive impact preview
- invalidation queue
- selective manuscript re-lint
- structural revalidation
- author dismissal

## M5 Isekai Pack

M5 provides:
- opt-in Earth-Origin Guard
- allowlists and custom terms
- World-Origin Mapping and source-place provenance
- travel / magic / economy / healing constraints
- M4/M4.5 integration

See docs/M5.md.

## M6 LN Genre Packs

M6 provides three independent, combinable packs.

Noble Lady:
- rank hierarchy
- house references
- rank/title consistency
- engagement graph
- address/etiquette checks

Palace/Harem:
- rank hierarchy
- faction references
- restricted-area permissions
- information-access permissions
- ritual sequence validation

Romantic Comedy:
- relationship-stage transitions
- schedule collision detection
- misunderstanding lifecycle

M6 also adds structural lint and structured dependency edges so setting-only changes are revalidated without relying only on manuscript text.

See docs/M6.md.

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
- docs/M6.md
- docs/ROADMAP.md

## Validation

Current M6 validation:
- 38 API tests passed
- Alembic upgrade succeeded through 0009
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
