# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Vietnamese education platform (RinoEdu) that summarises lesson reports and generates AI feedback using OpenAI. Two services: FastAPI backend (port 8000) and React + Vite frontend (port 5173). No database—data is local JSON files in `data/`. See `README.md` for endpoint reference.

### Running services

**Backend** (from `/workspace/backend`):
```bash
source /workspace/.venv/bin/activate
cd /workspace/backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Note: `python backend/app/main.py` does **not** work from the repo root because the app uses `from app.…` imports—always `cd backend` first or use `python -m uvicorn app.main:app`.

**Frontend** (from `/workspace/frontend`):
```bash
cd /workspace/frontend
npm run dev -- --port 5173
```

### Running tests

- **Backend**: `.venv/bin/python -m pytest backend/tests/ -v` (run from repo root)
- **Frontend**: `cd frontend && npx vitest run`

### Lint

- **Frontend**: `cd frontend && npx eslint .`
- There are 4 pre-existing `@typescript-eslint/no-unused-vars` errors in `App.tsx` (catch-clause variables `_error` and `_requestError`). These are in the existing codebase, not introduced by setup.

### Pre-existing test failures

10 of 14 frontend vitest tests fail because the tests query for buttons using `/nhan xet/i` (ASCII) but the rendered button text uses Vietnamese diacritics ("Nhận xét"). This is a pre-existing issue in the test suite.

### Environment variables

Copy `.env.example` to `.env` at repo root. The `OPENAI_API_KEY` secret is required for LLM calls but **not** for tests (all tests mock OpenAI) or the health endpoint. The backend reads `.env` via `python-dotenv`.

### Caching

Feedback results are cached as markdown files in `data/feedback_cache/`. Pre-existing cache files are committed, so clicking "Nhận xét" on lessons with cached data works without an `OPENAI_API_KEY`. Delete cache files to force fresh LLM generation.

### Python version

The backend requires Python 3.11 (per `backend/.python-version`). The venv is at `/workspace/.venv` and uses `python3.11`.
