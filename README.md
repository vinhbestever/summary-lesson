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
- `POST /api/v1/lesson-feedback`

Request (co the gui `report_text` hoac `report_url` hoac `lesson_id`):

```json
{
  "report_text": "Noi dung bao cao",
  "report_url": "https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id=3724970",
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

Request nhan xet lesson:

```json
{
  "lesson_id": "3724970",
  "lesson_label": "Lesson 3724970"
}
```

Response nhan xet lesson:

```json
{
  "lesson_label": "Lesson 3724970",
  "teacher_tone": "warm_encouraging",
  "overall_comment": "...",
  "session_breakdown": {
    "participation": { "score": 85, "comment": "...", "evidence": ["..."] },
    "pronunciation": { "score": 72, "comment": "...", "evidence": ["..."] },
    "vocabulary": { "score": 80, "comment": "...", "evidence": ["..."] },
    "grammar": { "score": 78, "comment": "...", "evidence": ["..."] },
    "reaction_confidence": { "score": 88, "comment": "...", "evidence": ["..."] }
  },
  "strengths": ["..."],
  "priority_improvements": [
    {
      "skill": "pronunciation",
      "priority": "high",
      "current_state": "...",
      "target_next_lesson": "...",
      "coach_tip": "..."
    }
  ],
  "next_lesson_plan": [{ "step": "...", "duration_minutes": 8 }],
  "parent_message": "..."
}
```

UI flow:
- Moi lesson card co nut `Nhan xet AI`.
- Bam nut de goi `/api/v1/lesson-feedback`.
- Ket qua hien thi o panel chung ben duoi danh sach lesson.
