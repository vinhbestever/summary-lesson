# Summary Lesson Monorepo

Frontend React + backend FastAPI de mo 2 link bao cao sau buoi hoc va tom tat noi dung bang LLM.

## Cau truc

- `frontend/`: React + Vite + TypeScript
- `backend/`: FastAPI + OpenAI

## Chay local

### 1) Backend

```bash
cd backend
uv sync --active 2>/dev/null || true
```

Neu ban chua co virtualenv, tu root repo co the chay:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r backend/requirements.txt
```

Sau do start API:

```bash
source .venv/bin/activate
python backend/app/main.py
```

API mac dinh: `http://localhost:8000`

### 2) Frontend

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

Frontend mac dinh: `http://localhost:5173`

## Endpoint

- `GET /health`
- `POST /api/v1/summaries`

Request:

```json
{
  "report_text": "Noi dung bao cao",
  "lesson_id": "TRIAL_LESSON_10_11"
}
```

Response:

```json
{
  "overall_summary": "...",
  "key_points": ["..."],
  "action_items": ["..."]
}
```
