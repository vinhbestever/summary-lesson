# Lesson Feedback LLM Design

Date: 2026-03-31
Status: Approved

## 1) Goal
Xây dựng luồng nhận xét cho từng lesson bằng LLM theo vai trò giáo viên tiếng Anh tiểu học, giọng điệu ấm áp - khích lệ. Người dùng bấm icon tại từng lesson option, hệ thống gọi LLM và hiển thị kết quả ở một panel chung bên dưới danh sách lesson.

## 2) Scope
- Bổ sung endpoint mới: `POST /api/v1/lesson-feedback`.
- Dùng raw lesson data làm input trực tiếp cho prompt (không bước chuẩn hóa riêng).
- Frontend thêm icon hành động cho từng lesson card.
- Kết quả hiển thị trong 1 panel chung dưới lesson list.

Out of scope:
- Không thay đổi/loại bỏ endpoint cũ `/api/v1/summaries`.
- Không thêm cơ chế lưu lịch sử nhận xét ở DB trong pha này.

## 3) Approach (Chosen)
Chosen approach: Prompt trực tiếp từ raw lesson JSON.

Lý do chọn:
- Nhanh triển khai, ít lớp trung gian.
- Phù hợp giai đoạn cần validate trải nghiệm nhận xét AI.

Trade-off chấp nhận:
- Độ ổn định output có thể dao động hơn so với phương án chuẩn hóa/rule-based.
- Cần schema validation + fallback kỹ ở backend để tránh vỡ UI.

## 4) API Design

### Endpoint
`POST /api/v1/lesson-feedback`

### Request
Cho phép tương thích với luồng hiện tại:
```json
{
  "lesson_id": "3724970",
  "report_url": "https://...",
  "report_text": "..."
}
```

Ưu tiên resolve input:
1. `report_text`
2. `report_url`
3. `lesson_id` -> build URL -> fetch

### Response Schema
```json
{
  "lesson_label": "Lesson 1",
  "teacher_tone": "warm_encouraging",
  "overall_comment": "string",
  "session_breakdown": {
    "participation": { "score": 0, "comment": "string", "evidence": ["string"] },
    "pronunciation": { "score": 0, "comment": "string", "evidence": ["string"] },
    "vocabulary": { "score": 0, "comment": "string", "evidence": ["string"] },
    "grammar": { "score": 0, "comment": "string", "evidence": ["string"] },
    "reaction_confidence": { "score": 0, "comment": "string", "evidence": ["string"] }
  },
  "strengths": ["string"],
  "priority_improvements": [
    {
      "skill": "pronunciation|vocabulary|grammar|reaction_confidence|participation",
      "priority": "high|medium|low",
      "current_state": "string",
      "target_next_lesson": "string",
      "coach_tip": "string"
    }
  ],
  "next_lesson_plan": [
    {
      "step": "string",
      "duration_minutes": 0
    }
  ],
  "parent_message": "string"
}
```

Validation rules:
- `score` trong khoảng 0-100.
- `priority_improvements` tối đa 3 mục.
- Field thiếu/không hợp lệ: backend trả fallback an toàn (`"chưa đủ dữ liệu"`) hoặc HTTP 500 nếu không thể chuẩn hóa.

## 5) Prompt Design

### System Prompt
```text
Bạn là giáo viên tiếng Anh tiểu học, giọng điệu ấm áp, tích cực, khích lệ.
Nhiệm vụ: nhận xét CHI TIẾT một buổi học từ dữ liệu lesson được cung cấp.

YÊU CẦU BẮT BUỘC:
1) Chỉ trả về JSON hợp lệ, không thêm markdown, không thêm giải thích ngoài JSON.
2) Dùng tiếng Việt tự nhiên, thân thiện với học sinh nhỏ và phụ huynh.
3) Mọi nhận xét phải dựa trên dữ liệu đầu vào. Nếu thiếu dữ liệu cho một ý, nêu rõ "chưa đủ dữ liệu".
4) Chấm điểm 0-100 cho từng mục trong session_breakdown.
5) Ưu tiên động viên trước, góp ý sau; góp ý phải cụ thể và có cách cải thiện.
6) Không dùng từ ngữ tiêu cực, phán xét.
7) Không suy diễn các thông tin không xuất hiện trong lesson.

THANG ĐIỂM GỢI Ý:
- 85-100: rất tốt, ổn định
- 70-84: tốt, còn vài điểm cần tối ưu
- 50-69: đạt cơ bản, cần luyện thêm
- 0-49: cần hỗ trợ nhiều hơn

OUTPUT PHẢI ĐÚNG SCHEMA:
<schema response>

DỮ LIỆU LESSON:
<raw lesson data>
```

### User Prompt
- Truyền `lesson_label` + raw lesson data làm nội dung chính.

## 6) Frontend UX
- Mỗi lesson card có icon `Nhận xét AI`.
- Click icon:
  - Disable icon lesson đang chạy.
  - Hiện trạng thái `Đang tạo nhận xét...`.
  - Gọi `POST /api/v1/lesson-feedback`.
- Render kết quả ở panel chung bên dưới list:
  - Nhận xét tổng quan.
  - Bảng điểm 5 tiêu chí.
  - Điểm mạnh.
  - Ưu tiên cải thiện.
  - Kế hoạch buổi sau.
  - Lời nhắn phụ huynh.
- Click lesson khác: panel cập nhật nội dung mới (không mở modal, không inline từng card).

## 7) Error Handling
Backend:
- `400`: thiếu input hợp lệ.
- `502`: fetch report lỗi.
- `500`: lỗi LLM hoặc parse/schema lỗi.

Frontend:
- Panel hiển thị thông báo thân thiện: `Chưa tạo được nhận xét. Vui lòng thử lại.`
- Có hành động `Thử lại`.
- Không để vỡ layout khi response thiếu trường.

## 8) Testing Plan
1. API contract test: response đúng đủ schema.
2. Prompt behavior test:
- Lesson tốt: nhận xét tích cực, góp ý nhẹ.
- Lesson yếu: tone vẫn ấm áp, có hướng cải thiện rõ.
3. Frontend integration:
- Click icon gọi đúng endpoint.
- Loading/error/success hiển thị đúng panel chung.
- Click liên tiếp nhiều lesson: panel giữ lesson mới nhất.
4. Regression:
- `/api/v1/summaries` cũ vẫn hoạt động.

## 9) Risks and Mitigations
- Rủi ro output dao động vì raw data dài/nhiễu.
  - Giảm thiểu: temperature thấp, schema validation chặt, fallback text an toàn.
- Rủi ro token cost tăng khi lesson lớn.
  - Giảm thiểu: có thể cắt bớt field không cần thiết ở pha sau nếu cần tối ưu.

## 10) Acceptance Criteria
- Người dùng bấm icon tại mỗi lesson để nhận xét AI.
- Kết quả hiển thị đúng panel chung dưới danh sách lesson.
- Nội dung đúng tone giáo viên ấm áp, có điểm số từng mục, có khuyến nghị cụ thể.
- Hệ thống xử lý ổn định các trạng thái loading/error và không ảnh hưởng endpoint summary hiện có.
