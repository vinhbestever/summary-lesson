# Portfolio Feedback Design (Nhan Xet Chung Toan Bo Buoi Hoc)

## Muc tieu
Them mot nut `Nhan xet chung` o man hinh chinh de tao nhan xet tong hop cho toan bo qua trinh hoc hien co trong he thong, du lieu dau vao lay tu toan bo file `data/lesson_*.json`. Luong xu ly van dung LLM va stream tien do ve frontend.

## Pham vi
- Co: Backend API tong hop moi (stream + non-stream), schema response moi, frontend nut moi va panel hien thi ket qua tong hop.
- Khong: thay doi luong nhan xet tung buoi hien tai.

## Yeu cau da chot
- Nguon du lieu: Tat ca file `data/lesson_*.json`.
- Schema: Dung schema moi rieng cho tong hop (khong dung lai schema buoi don).
- Trai nghiem: Co stream giong luong hien tai.

## Phuong an duoc chon
Chon phuong an tach endpoint rieng cho portfolio feedback:
- `POST /api/v1/portfolio-feedback`
- `POST /api/v1/portfolio-feedback/stream`

Ly do chon:
- Tach ro rang “nhan xet 1 buoi” va “nhan xet toan bo qua trinh”.
- Don gian hoa validation va su dung schema rieng.
- De mo rong sau nay (trend, milestone, cohort benchmark) ma khong lam roi endpoint cu.

## Thiet ke backend

### 1) Ingest du lieu
Them ham moi trong `backend/app/ingest.py`:
- `load_all_lessons_json_from_local_data() -> list[dict[str, str]]`

Hanh vi:
- Quet thu muc `data/` voi pattern `lesson_*.json`.
- Doc noi dung text cua tung file.
- Tra ve danh sach doi tuong:
  - `lesson_id`
  - `source_file`
  - `raw_json_text`
- Sap xep on dinh theo ten file tang dan.
- Bo qua file rong; neu khong co du lieu hop le thi bao loi o layer API.

### 2) Schema moi cho portfolio
Them trong `backend/app/schemas.py`:
- `SkillTrend`
  - `current_level: str`
  - `trend: Literal['improving', 'stable', 'declining', 'mixed', 'insufficient_data']`
  - `evidence: list[str]`
  - `recommendation: str`
- `PortfolioSkillTrends`
  - `participation`, `pronunciation`, `vocabulary`, `grammar`, `reaction_confidence`: `SkillTrend`
- `PortfolioPriorityImprovement`
  - `skill` (giu enum nhu he thong cu)
  - `priority: Literal['high', 'medium', 'low']`
  - `reason: str`
  - `next_2_weeks_target: str`
  - `coach_tip: str`
- `StudyPlanStep`
  - `step: str`
  - `frequency: str`
  - `duration_minutes: int`
- `DateRange`
  - `from_date: str`
  - `to_date: str`
- `PortfolioFeedbackResponse`
  - `portfolio_label: str`
  - `total_lessons: int`
  - `date_range: DateRange | None`
  - `overall_assessment: str`
  - `skill_trends: PortfolioSkillTrends`
  - `top_strengths: list[str]`
  - `top_priorities: list[PortfolioPriorityImprovement]`
  - `study_plan_2_weeks: list[StudyPlanStep]`
  - `parent_message: str`

### 3) LLM logic cho portfolio
Them trong `backend/app/llm.py`:
- `generate_portfolio_feedback(lessons_payload: list[dict[str, str]], portfolio_label: str | None = None)`
- `stream_portfolio_feedback(...)`
- bo normalize va fallback cho schema moi, tuong tu luong lesson feedback.

Prompt dinh huong:
- Dong vai giao vien danh gia tien trinh hoc theo nhieu buoi.
- Bat buoc rut ra trend cho 5 ky nang.
- Uu tien nhan xet co bang chung theo buoi (evidence), khong suy dien vuot du lieu.
- Bat buoc JSON hop le, khong markdown.

Gioi han payload:
- Neu so buoi qua lon, cat theo gioi han an toan (VD 30 buoi moi nhat theo ten file sap xep), kem metadata de LLM biet da gioi han.

### 4) API routes
Them trong `backend/app/main.py`:
- `POST /api/v1/portfolio-feedback`
- `POST /api/v1/portfolio-feedback/stream`

Hanh vi:
- Tu dong load tat ca lesson local qua ingest moi.
- Neu khong co du lieu: tra loi 400/500 co message ro rang.
- Stream su dung cung format SSE hien tai:
  - `status`, `chunk`, `result`, `error`, `done`

## Thiet ke frontend

### 1) Nut moi o man chinh
Trong `frontend/src/App.tsx`:
- Them nut `Nhan xet chung` o khu vuc header tren danh sach card.
- Khi dang loading bat ky luong nao, disable tat ca nut nhan xet.

### 2) State va mode hien thi
- Them state mode:
  - `feedbackMode: 'lesson' | 'portfolio' | null`
- Them state ket qua tong hop:
  - `portfolioFeedback` theo schema moi.
- Tiep tuc dung chung state stream (`feedbackStreamingStatus`, `feedbackStreamingText`) de tan dung UI progress hien co.

### 3) Stream UX cho portfolio
- Goi endpoint `/api/v1/portfolio-feedback/stream`.
- Doi section chips theo ngu canh tong hop:
  - Tong quan, Xu huong ky nang, Diem manh, Uu tien, Ke hoach 2 tuan, Loi nhan phu huynh.
- Preview card doc tu stream text:
  - `overall_assessment`, `top_strengths`, `parent_message`.

### 4) Result panel portfolio
Them panel rieng hien:
- Tieu de: `Nhan xet chung qua trinh hoc`.
- Metadata: `Tong so buoi`, `Khoang thoi gian`.
- Block `skill_trends` cho 5 ky nang.
- `top_strengths`, `top_priorities`, `study_plan_2_weeks`, `parent_message`.

## Xu ly loi va fallback
- Khong co du lieu lesson local: thong bao loi than thien, de hieu.
- Loi LLM hoac stream: hien `feedbackError` nhu luong cu.
- Neu field nao thieu do LLM: normalize ve gia tri fallback thay vi crash.

## Kiem thu

### Backend
- `backend/tests/test_api.py`:
  - test create portfolio feedback thanh cong.
  - test stream portfolio feedback co `result` va `done`.
  - test khi khong co du lieu tra loi loi dung.
- Co the can mock OpenAI/LLM nhu luong hien tai.

### Frontend
- `frontend/src/App.test.tsx`:
  - hien nut `Nhan xet chung`.
  - bam nut goi dung endpoint stream portfolio.
  - render panel ket qua portfolio khi co payload.

## Anh huong tai lieu
Cap nhat `README.md`:
- Them endpoint moi.
- Them mo ta UI flow moi (nut nhan xet chung).

## Tieu chi hoan tat
- Co nut `Nhan xet chung` tren man hinh chinh.
- Bam nut sinh nhan xet tong hop tu toan bo file `data/lesson_*.json`.
- Stream hoat dong, co trang thai va hien ket qua cuoi dung schema moi.
- Luong nhan xet tung buoi cu van hoat dong binh thuong.
