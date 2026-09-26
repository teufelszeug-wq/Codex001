# Creative Consistency OS

A local-first creative production system for long-form fiction: World Builder + Story Bible + Writing Environment + Continuity/Lint + Change Management.

## Current progress

- M0 Foundation — complete
- M1 Application Foundation — complete
- M2 World Builder Alpha — complete
- M2.5 Language & Culture Builder — next

## M2 Golden Path

Genre → Setup Mode → World DNA → Review → Persisted Project

Genre selection supports multiple genres, weights, custom genres and "undecided." There is no mandatory primary genre. Every World DNA section can be AUTO, MANUAL or SKIP.

AUTO is proposal permission only; it never commits generated content to Canon.

## Structure

- apps/web — Next.js + TypeScript
- apps/api — FastAPI + SQLAlchemy + Alembic
- docs/M1.md
- docs/M2.md
- docs/ROADMAP.md

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