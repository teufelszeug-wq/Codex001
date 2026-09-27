# Creative Consistency OS

A local-first creative production system for long-form fiction: World Builder + Language/Culture + Story Bible + Writing Room + Entity Intelligence + Continuity/Lint + Change Management.

## Current progress

- M0 Foundation — complete
- M1 Application Foundation — complete
- M2 World Builder Alpha — complete
- M2.5 Language & Culture Builder — complete
- M3 Story Bible + Writing Room — complete
- M3.5 Entity Intelligence — complete
- M4 Core Lint Engine — next

## Current Golden Path

Genre → Setup Mode → World DNA → Language/Culture → Story Bible → Writing Room → Entity Intelligence → Lint

The project now supports structured world-building, fictional-language/culture design, author-controlled Canon states, chapter writing with autosave and revision history, a basic timeline, aliases, revision-bound manuscript mentions, ambiguity-aware reference resolution, candidate-to-INFERENCE promotion and entity relations.

Author-control rule: generated, extracted or inferred material never becomes CANON automatically.

## Current schema

Project schema version: 5

Migrations:
- 0001 M1 baseline
- 0002 World Builder Alpha
- 0003 Language & Culture Builder
- 0004 Story Bible + Writing Room
- 0005 Entity Intelligence

## Structure

- apps/web — Next.js + TypeScript
- apps/api — FastAPI + SQLAlchemy + Alembic
- docs/M1.md
- docs/M2.md
- docs/M2.5.md
- docs/M3.md
- docs/M3.5.md
- docs/ROADMAP.md

## Validation

Current M3/M3.5 branch validation:
- 18 API tests passed
- Alembic upgrade succeeded
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
