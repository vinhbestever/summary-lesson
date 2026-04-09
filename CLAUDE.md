# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend

```bash
# Start (must cd into backend first — uses `from app.…` imports)
source .venv/bin/activate
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Tests (run from repo root)
.venv/bin/python -m pytest backend/tests/ -v

# Install deps
uv venv .venv
uv pip install --python .venv/bin/python -r backend/requirements.txt
```

### Frontend

```bash
cd frontend
npm install
npm run dev -- --port 5173   # dev server at http://localhost:5173
npx eslint .                  # lint
npx vitest run                # tests
```

## Architecture

**Monorepo**: `backend/` (FastAPI, port 8000) + `frontend/` (React + Vite, port 5173). No database — lesson data lives in `data/lesson_*.json` files.

### Backend (`backend/app/`)

- `main.py` — FastAPI app with CORS; all route handlers. Parses radar-chart rubric scores (proficiency/capacity/engagement/self_regulation) from lesson JSON markdown fields using `_LEVEL_SCORE_MAP`.
- `llm.py` — OpenAI calls (`gpt-4.1-mini` by default via `OPENAI_MODEL` env var). Four entry points: `summarize_report`, `generate_lesson_feedback`, `stream_lesson_feedback`, `generate_portfolio_feedback`, `stream_portfolio_feedback`. Streaming endpoints return plain markdown via `StreamingResponse`.
- `ingest.py` — Fetches lesson report HTML/text from RinoEdu URLs using `VITE_REPORT_TOKEN`; also loads local `data/lesson_*.json` files.
- `feedback_cache.py` — Markdown cache in `data/feedback_cache/`. Cache key versioning: `LESSON_FEEDBACK_CACHE_VERSION = 'v11'`, `PORTFOLIO_FEEDBACK_CACHE_VERSION = 'v2'`. Delete cache files to force fresh LLM generation.
- `rubric_quality.py` — Builds data-quality signals appended to LLM prompts (signals thin data, requires confidence level + remediation).
- `schemas.py` — Pydantic request/response models.

### Frontend (`frontend/src/`)

- Single-component app (`App.tsx`). Loads all `data/lesson_*.json` at build time via `import.meta.glob`. Renders lesson cards with radar chart scores parsed client-side from the same JSON.
- Each lesson card has a "Nhận xét" button that calls `/api/v1/lesson-feedback/stream` (streaming markdown).
- "Nhận xét chung" button calls `/api/v1/portfolio-feedback/stream` for aggregate feedback.
- Streaming responses are rendered with `react-markdown` + `remark-gfm` into a shared panel below the card list.

### Data flow

```
data/lesson_<id>.json  →  frontend (radar chart scores)
                       →  backend ingest.py (lesson content for LLM)
                       →  data/feedback_cache/<key>.md (cached LLM output)
```

## Environment

Copy `.env.example` to `.env` at repo root. `OPENAI_API_KEY` is required for LLM calls but not for tests (all tests mock OpenAI) or the health endpoint.

## Known issues

- **10/14 frontend tests fail**: Tests query buttons with `/nhan xet/i` (no diacritics) but rendered text uses "Nhận xét". Pre-existing issue in the test suite.
- **4 ESLint warnings**: `@typescript-eslint/no-unused-vars` on catch-clause variables `_error`/`_requestError` in `App.tsx`. Pre-existing.
- **Import path**: `python backend/app/main.py` from repo root does not work; always use `python -m uvicorn app.main:app` from within `backend/`.
