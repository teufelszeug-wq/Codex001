# Creative Consistency OS

M1 Application Foundation for a long-form fiction world-building and continuity platform.

## M1 scope
- Local-first modular monolith
- Next.js/TypeScript web shell
- FastAPI API
- SQLite behind a repository layer
- Alembic migration baseline
- Canon/provenance primitives
- ChangeLog foundation
- Health endpoint, tests, and CI

## Local API
```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Windows activation: `.venv\Scripts\activate`.

## Local web
```bash
cd apps/web
npm install
npm run dev
```

Default API URL: `http://localhost:8000`.
See `docs/M1.md` for the milestone record.
