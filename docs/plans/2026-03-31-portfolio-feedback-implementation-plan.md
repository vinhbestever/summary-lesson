# Portfolio Feedback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Them luong `Nhan xet chung` tren man hinh chinh de tong hop tat ca du lieu `data/lesson_*.json`, stream qua backend va hien thi panel danh gia toan bo qua trinh hoc.

**Architecture:** Backend FastAPI them ingest all lessons, schema portfolio rieng, va 2 endpoint `POST /api/v1/portfolio-feedback` + `/api/v1/portfolio-feedback/stream` goi LLM voi prompt tong hop nhieu buoi. Frontend React them nut `Nhan xet chung`, mode hien thi rieng cho portfolio, tai su dung SSE parser/loading panel, va render ket qua theo schema moi. Toan bo trien khai theo TDD tung buoc nho va commit nho.

**Tech Stack:** Python 3 + FastAPI + Pydantic + OpenAI SDK, React + TypeScript + Vite, pytest, Vitest + Testing Library.

---

### Task 1: Add Local Data Aggregation for All Lessons

**Files:**
- Modify: `backend/app/ingest.py`
- Test: `backend/tests/test_api.py`

**Step 1: Write the failing test**

Them test cho ham ingest moi (qua API hoac import truc tiep):

```python
def test_load_all_lessons_json_from_local_data_returns_sorted_items(tmp_path, monkeypatch):
    ...
```

Assert:
- Chi lay file `lesson_*.json`
- Tra ve list co `lesson_id`, `source_file`, `raw_json_text`
- Thu tu sap xep on dinh theo ten file

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_api.py -k load_all_lessons -v`
Expected: FAIL (ham chua ton tai)

**Step 3: Write minimal implementation**

Trong `backend/app/ingest.py` them:

```python
def load_all_lessons_json_from_local_data() -> list[dict[str, str]]:
    ...
```

Rules:
- Quet `data/lesson_*.json`
- Bo qua noi dung rong
- Sap xep theo ten file tang dan

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_api.py -k load_all_lessons -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/ingest.py backend/tests/test_api.py
git commit -m "feat: add local ingest for all lesson json files"
```

### Task 2: Define Portfolio Feedback Schemas

**Files:**
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_api.py`

**Step 1: Write the failing schema/API test**

```python
def test_create_portfolio_feedback_returns_expected_schema(client, monkeypatch):
    ...
```

Assert response keys:
- `portfolio_label`, `total_lessons`, `date_range`, `overall_assessment`
- `skill_trends` (5 skills)
- `top_strengths`, `top_priorities`, `study_plan_2_weeks`, `parent_message`

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_api.py::test_create_portfolio_feedback_returns_expected_schema -v`
Expected: FAIL (schema/route chua co)

**Step 3: Add schema models**

Trong `backend/app/schemas.py` them:
- `SkillTrend`
- `PortfolioSkillTrends`
- `PortfolioPriorityImprovement`
- `StudyPlanStep`
- `DateRange`
- `PortfolioFeedbackResponse`

Them validators can thiet:
- gioi han `duration_minutes`
- priority enum, skill enum
- strip text fields

**Step 4: Run focused test again**

Run: `pytest backend/tests/test_api.py::test_create_portfolio_feedback_returns_expected_schema -v`
Expected: FAIL voi ly do route/chuc nang chua co (schema compile OK)

**Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_api.py
git commit -m "feat: add portfolio feedback response schemas"
```

### Task 3: Implement Portfolio LLM Generator + Stream

**Files:**
- Modify: `backend/app/llm.py`
- Test: `backend/tests/test_api.py`

**Step 1: Write failing tests for non-stream and stream**

```python
def test_generate_portfolio_feedback_normalizes_output(...):
    ...

def test_stream_portfolio_feedback_emits_result_event(...):
    ...
```

Mock OpenAI de tra JSON co chu y cac truong trend/priority.

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_api.py -k portfolio_feedback_llm -v`
Expected: FAIL

**Step 3: Implement minimal LLM functions**

Trong `backend/app/llm.py` them:
- `_build_portfolio_feedback_messages(...)`
- `_normalize_portfolio_feedback_payload(...)`
- `generate_portfolio_feedback(...)`
- `stream_portfolio_feedback(...)`

Yeu cau:
- output JSON object
- fallback an toan neu field thieu
- stream event format dong bo voi luong cu (`status/chunk/result`)

**Step 4: Run focused tests**

Run: `pytest backend/tests/test_api.py -k portfolio_feedback_llm -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/llm.py backend/tests/test_api.py
git commit -m "feat: add llm portfolio feedback generator and stream"
```

### Task 4: Add Portfolio API Endpoints

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api.py`

**Step 1: Write failing endpoint tests**

Them tests:
- `POST /api/v1/portfolio-feedback` success
- `POST /api/v1/portfolio-feedback/stream` success co `result` + `done`
- error khi khong co file lesson hop le

```python
def test_create_portfolio_feedback_success(client, monkeypatch):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_api.py -k portfolio_feedback_api -v`
Expected: FAIL

**Step 3: Implement routes**

Trong `backend/app/main.py`:
- import ingest moi + schema moi + llm moi
- them 2 endpoints portfolio
- map loi ro rang (`HTTPException` voi message phu hop)
- stream SSE dung helper `_format_sse_event`

**Step 4: Run backend tests**

Run: `pytest backend/tests -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat: add portfolio feedback api endpoints"
```

### Task 5: Add Portfolio Feedback UI Flow

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`
- Modify: `frontend/src/App.test.tsx`

**Step 1: Write failing frontend tests**

Them tests:
- Hien nut `Nhan xet chung`
- Bam nut goi `/api/v1/portfolio-feedback/stream`
- Hien loading stream va render result panel portfolio
- Error state khi API loi

```tsx
it('requests portfolio feedback stream and renders portfolio panel', async () => {
  ...
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- App.test.tsx`
Expected: FAIL

**Step 3: Implement minimal UI**

Trong `frontend/src/App.tsx`:
- Them type `PortfolioFeedbackPayload`
- Them state `feedbackMode`, `portfolioFeedback`
- Them handler `handleGeneratePortfolioFeedback`
- Tai su dung SSE parser, tách section labels theo mode
- Render panel ket qua portfolio rieng

Trong `frontend/src/App.css`:
- Style nut moi va block trend/metadata

**Step 4: Run frontend tests/build**

Run:
- `cd frontend && npm run test -- App.test.tsx`
- `cd frontend && npm run build`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.css frontend/src/App.test.tsx
git commit -m "feat: add portfolio feedback button and result panel"
```

### Task 6: Documentation + Final Verification

**Files:**
- Modify: `README.md`
- Optional touch if needed: `backend/tests/test_api.py`, `frontend/src/App.test.tsx`

**Step 1: Update README**

Them:
- endpoint moi `/api/v1/portfolio-feedback` va `/api/v1/portfolio-feedback/stream`
- mo ta nut `Nhan xet chung` va nguon du lieu `data/lesson_*.json`

**Step 2: Run full verification**

Run from repo root:

```bash
pytest backend/tests -v
cd frontend && npm run test -- App.test.tsx
cd frontend && npm run build
```

Expected:
- Backend tests PASS
- Frontend tests PASS
- Frontend build PASS

**Step 3: Final commit**

```bash
git add README.md
git commit -m "docs: add portfolio feedback api and ui flow"
```

**Step 4: Prepare handoff notes**

Ghi ro:
- input source (`data/lesson_*.json`)
- schema moi va truong chinh
- limitation neu payload lon va cach cat gioi han
