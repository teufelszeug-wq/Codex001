# Creative Consistency OS

A local-first creative production system for long-form fiction: World Builder + Language/Culture + Story Bible + Writing Environment + Continuity/Lint + Change Management.

## Current progress

- M0 Foundation — complete
- M1 Application Foundation — complete
- M2 World Builder Alpha — complete
- M2.5 Language & Culture Builder — implementation complete
- M3 Bible + Writing Room — next after the M2.5 CI gate

## Current Golden Path

Genre → Setup Mode → World DNA → Language/Culture → Persisted Project

M2.5 supports multiple fictional languages, weighted inspiration mixes, custom inspiration, phonology, naming rules, scripts, culture mapping, language contact, root lexicon, reader-facing rendering, and Earth-origin terminology policy.

Presets are optional. Common language is optional. Generated name previews never become Canon automatically.

## Structure

- apps/web — Next.js + TypeScript
- apps/api — FastAPI + SQLAlchemy + Alembic
- docs/M1.md
- docs/M2.md
- docs/M2.5.md
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
