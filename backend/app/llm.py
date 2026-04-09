import json
import os
from typing import Any

from openai import OpenAI

VALID_PRIORITY_SKILLS = {'proficiency', 'capacity', 'engagement', 'self_regulation'}
VALID_PRIORITIES = {'high', 'medium', 'low'}
VALID_TRENDS = {'improving', 'stable', 'declining', 'mixed', 'insufficient_data'}


def summarize_report(report_text: str) -> dict[str, Any]:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')

    system_prompt = (
        'Ban la tro ly tom tat bao cao buoi hoc. '
        'Tra ve duy nhat JSON hop le voi 3 truong: '
        'overall_summary (string), key_points (array string), action_items (array string). '
        'Su dung tieng Viet ngan gon, ro rang.'
    )

    completion = client.chat.completions.create(
        model=model,
        response_format={'type': 'json_object'},
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': report_text},
        ],
        temperature=0.2,
    )

    content = completion.choices[0].message.content
    if not content:
        raise ValueError('LLM returned an empty response')

    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError('LLM output is not a JSON object')

    required_fields = ('overall_summary', 'key_points', 'action_items')
    for field in required_fields:
        if field not in parsed:
            raise ValueError(f'Missing field in LLM response: {field}')

    return {
        'overall_summary': str(parsed['overall_summary']).strip(),
        'key_points': [str(item).strip() for item in parsed['key_points']],
        'action_items': [str(item).strip() for item in parsed['action_items']],
    }


def _normalize_text(value: Any, fallback: str = 'chua du du lieu') -> str:
    text = str(value).strip() if value is not None else ''
    return text or fallback


def _normalize_score(value: Any) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_priority_item(value: Any) -> dict[str, str] | None:
    source = value if isinstance(value, dict) else {}
    skill = str(source.get('skill', '')).strip()
    priority = str(source.get('priority', '')).strip()
    if skill not in VALID_PRIORITY_SKILLS or priority not in VALID_PRIORITIES:
        return None
    return {
        'skill': skill,
        'priority': priority,
        'current_state': _normalize_text(source.get('current_state')),
        'target_next_lesson': _normalize_text(source.get('target_next_lesson')),
        'coach_tip': _normalize_text(source.get('coach_tip')),
    }


def _normalize_session_criterion(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    evidence = _normalize_string_list(source.get('evidence'))
    if not evidence:
        evidence = ['chua du du lieu']
    return {
        'score': _normalize_score(source.get('score')),
        'comment': _normalize_text(source.get('comment')),
        'evidence': evidence,
    }


def _normalize_trend(value: Any) -> str:
    trend = str(value).strip()
    if trend in VALID_TRENDS:
        return trend
    return 'insufficient_data'


def _normalize_skill_trend(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    evidence = _normalize_string_list(source.get('evidence'))
    return {
        'current_level': _normalize_text(source.get('current_level'), fallback=''),
        'trend': _normalize_trend(source.get('trend')),
        'evidence': evidence,
        'recommendation': _normalize_text(source.get('recommendation'), fallback=''),
    }


def _normalize_portfolio_priority_item(value: Any) -> dict[str, str] | None:
    source = value if isinstance(value, dict) else {}
    skill = str(source.get('skill', '')).strip()
    priority = str(source.get('priority', '')).strip()
    if skill not in VALID_PRIORITY_SKILLS or priority not in VALID_PRIORITIES:
        return None
    return {
        'skill': skill,
        'priority': priority,
        'reason': _normalize_text(source.get('reason'), fallback=''),
        'next_2_weeks_target': _normalize_text(source.get('next_2_weeks_target'), fallback=''),
        'coach_tip': _normalize_text(source.get('coach_tip'), fallback=''),
    }


def _normalize_study_plan_item(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    return {
        'step': _normalize_text(source.get('step'), fallback=''),
        'frequency': _normalize_text(source.get('frequency'), fallback=''),
        'duration_minutes': _normalize_score(source.get('duration_minutes')),
    }


def _normalize_date_range(value: Any) -> dict[str, str] | None:
    source = value if isinstance(value, dict) else {}
    from_date = _normalize_text(source.get('from_date'), fallback='').strip()
    to_date = _normalize_text(source.get('to_date'), fallback='').strip()
    if not from_date and not to_date:
        return None
    return {
        'from_date': from_date,
        'to_date': to_date,
    }


def _parse_lesson_root(raw_json_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_json_text)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return parsed[0]
    return {}


def _extract_primary_report(root: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(root, dict):
        return {}
    reports = root.get('reports')
    if isinstance(reports, list):
        for item in reports:
            if isinstance(item, dict):
                return item
        return {}
    return root


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _build_portfolio_input_context(lessons_payload: list[dict[str, str]]) -> dict[str, Any]:
    lesson_summaries: list[dict[str, Any]] = []
    pronunciation_scores: list[float] = []
    speaking_turns: list[float] = []
    speaking_coverage_values: list[float] = []
    reaction_times: list[float] = []
    completion_percent_values: list[float] = []

    for item in lessons_payload:
        lesson_id = _normalize_text(item.get('lesson_id', ''), fallback='unknown')
        source_file = _normalize_text(item.get('source_file', ''), fallback='unknown')
        root = _parse_lesson_root(item.get('raw_json_text', ''))
        report = _extract_primary_report(root)
        achievements = report.get('achievements') if isinstance(report, dict) else {}
        achievements = achievements if isinstance(achievements, dict) else {}
        stats = achievements.get('stats') if isinstance(achievements.get('stats'), dict) else {}
        pronunciation = achievements.get('pronunciation') if isinstance(achievements.get('pronunciation'), dict) else {}

        speaking_turn_count = _as_int(stats.get('speakingTurnCount'))
        speaking_coverage = _as_float(stats.get('speakingCoverage'))
        reaction_time_ms = _as_float(stats.get('averageReactionTimeMs'))
        completion_percent = _as_float(stats.get('sectionsCompletionPercent'))
        average_pronunciation_score = _as_float(pronunciation.get('averagePronunciationScore'))
        teacher_comment = _normalize_text(stats.get('teacherComment'))
        session_summary = _normalize_text(stats.get('sessionSummary'))
        trial_comment = _normalize_text(stats.get('trialComment'))

        if speaking_turn_count is not None:
            speaking_turns.append(float(speaking_turn_count))
        if speaking_coverage is not None:
            speaking_coverage_values.append(speaking_coverage)
        if reaction_time_ms is not None:
            reaction_times.append(reaction_time_ms)
        if completion_percent is not None:
            completion_percent_values.append(completion_percent)
        if average_pronunciation_score is not None:
            pronunciation_scores.append(average_pronunciation_score)

        lesson_summaries.append(
            {
                'lesson_id': lesson_id,
                'source_file': source_file,
                'speaking_turn_count': speaking_turn_count,
                'speaking_coverage': speaking_coverage,
                'average_reaction_time_ms': reaction_time_ms,
                'sections_completion_percent': completion_percent,
                'average_pronunciation_score': average_pronunciation_score,
                'teacher_comment': teacher_comment,
                'session_summary': session_summary,
                'trial_comment': trial_comment,
            }
        )

    evidence_highlights = []
    for summary in lesson_summaries:
        lesson_ref = f"{summary['lesson_id']} ({summary['source_file']})"
        pronunciation_text = summary['average_pronunciation_score']
        speaking_turn_text = summary['speaking_turn_count']
        reaction_text = summary['average_reaction_time_ms']
        completion_text = summary['sections_completion_percent']
        evidence_highlights.append(
            f"{lesson_ref}: pronunciation_avg={pronunciation_text}, speaking_turns={speaking_turn_text}, "
            f"reaction_ms={reaction_text}, completion_percent={completion_text}"
        )

    return {
        'total_lessons': len(lesson_summaries),
        'lesson_summaries': lesson_summaries,
        'aggregates': {
            'pronunciation_score_avg': _avg(pronunciation_scores),
            'speaking_turn_avg': _avg(speaking_turns),
            'speaking_coverage_avg': _avg(speaking_coverage_values),
            'reaction_time_avg_ms': _avg(reaction_times),
            'sections_completion_percent_avg': _avg(completion_percent_values),
        },
        'planning_hints': {
            'weak_skill_signals': [
                {
                    'criterion': 'proficiency',
                    'signal': 'Diem noi/doc/nghe thap, tu vung/ngu phap yeu, lap lai loi co ban',
                    'target_2_weeks': 'Cung co kien thuc trong tam, giam loi lap lai qua luyen tap co huong dan',
                },
                {
                    'criterion': 'capacity',
                    'signal': 'Phan xa cham, hoan thanh cham so voi lop, can nhac nhieu lan',
                    'target_2_weeks': 'Tang nhip tiep thu va hoan thanh phan co ban dung tien do',
                },
                {
                    'criterion': 'engagement',
                    'signal': 'It luot noi, it phan hoi, tham gia thu dong',
                    'target_2_weeks': 'Khuyen khich hoi dap nhanh va tham gia hoat dong/nhom ro rang hon',
                },
                {
                    'criterion': 'self_regulation',
                    'signal': 'Can nhac de bat dau, de mat tap trung, de bo task hoac bo trong bai',
                    'target_2_weeks': 'Luyen vao bai ngay, tu kiem tra truoc khi nop, xoay xo khi gap kho',
                },
            ],
            'must_link_plan_to_context': True,
        },
        'evidence_highlights': evidence_highlights,
    }


def _has_actionable_portfolio_plan(payload: dict[str, Any]) -> bool:
    plan = payload.get('study_plan_2_weeks')
    if not isinstance(plan, list) or len(plan) < 4:
        return False
    valid_items = 0
    for item in plan:
        if not isinstance(item, dict):
            continue
        step = str(item.get('step', '')).strip()
        frequency = str(item.get('frequency', '')).strip()
        duration = _normalize_score(item.get('duration_minutes'))
        if step and frequency and duration > 0:
            valid_items += 1
    return valid_items >= 4


def _parse_json_object_or_raise(raw_content: str) -> dict[str, Any]:
    if not raw_content:
        raise ValueError('LLM returned an empty response')
    parsed = json.loads(raw_content)
    if not isinstance(parsed, dict):
        raise ValueError('LLM output is not a JSON object')
    return parsed


def _request_json_completion(client: OpenAI, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    completion = client.chat.completions.create(
        model=model,
        response_format={'type': 'json_object'},
        messages=messages,
        temperature=0.2,
    )
    content = completion.choices[0].message.content
    return _parse_json_object_or_raise(content or '')


def _build_portfolio_plan_repair_messages(
    lessons_payload: list[dict[str, str]], portfolio_label: str | None, current_output: dict[str, Any]
) -> list[dict[str, str]]:
    context = _build_portfolio_input_context(lessons_payload)
    system_prompt = (
        'Ban dang sua output JSON nhan xet tong hop. '
        'Yeu cau bat buoc: khong doi schema, khong bịa du lieu. '
        'Tap trung sua top_priorities va study_plan_2_weeks dua tren portfolio_context va evidence_highlights. '
        'study_plan_2_weeks bat buoc 6-8 buoc, moi buoc phai co step cu the, frequency ro rang, duration_minutes 8-20. '
        'Moi buoc can lien ket toi it nhat 1 tieu chi (proficiency/capacity/engagement/self_regulation) co trong planning_hints. '
        'Khong duoc de rong.'
    )
    user_payload = {
        'portfolio_label': portfolio_label or 'Tong hop qua trinh hoc',
        'portfolio_context': context,
        'current_output': current_output,
        'task': 'Rebuild full JSON with the same schema, but regenerate top_priorities and study_plan_2_weeks to be actionable and data-grounded.',
    }
    return [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
    ]


def _build_fallback_next_lesson_plan(priorities: list[dict[str, str]]) -> list[dict[str, Any]]:
    default_by_skill = {
        'proficiency': {'step': 'Cung co kien thuc trong tam: on tu/cau mau va luyen noi co kiem tra loi', 'duration_minutes': 12},
        'capacity': {'step': 'Tang nhip tiep thu: hoan thanh phan co ban theung tien do, giam thoi gian phan hoi', 'duration_minutes': 10},
        'engagement': {'step': 'Khuyen khich tham gia chu dong: hoi dap nhanh va gop y trong hoat dong nhom', 'duration_minutes': 8},
        'self_regulation': {'step': 'Luyen tu vao bai, tu kiem tra truoc khi nop, khong bo trong khi gap kho', 'duration_minutes': 10},
    }
    plan: list[dict[str, Any]] = []
    for item in priorities[:3]:
        skill = item.get('skill', '')
        suggestion = default_by_skill.get(skill)
        if suggestion:
            plan.append(suggestion)
    if not plan:
        plan = [
            {'step': 'Khoi dong on tu vung cu va cau don gian', 'duration_minutes': 8},
            {'step': 'Luyen phat am trong tam theo tu va cum tu', 'duration_minutes': 12},
            {'step': 'Tong ket bang hoi dap ngan va nhan xet cuoi buoi', 'duration_minutes': 8},
        ]
    return plan


def _build_lesson_feedback_messages(report_text: str, lesson_label: str | None) -> list[dict[str, str]]:
    lesson_input: Any = report_text
    try:
        parsed = json.loads(report_text)
        if isinstance(parsed, (dict, list)):
            lesson_input = parsed
    except (json.JSONDecodeError, TypeError):
        lesson_input = report_text

    system_prompt = (
        'Bạn là giáo viên tiếng Anh tiểu học nhiều kinh nghiệm, giọng điệu ấm áp và khích lệ. '
        'Nhiệm vụ: viết nhận xét buổi học bằng markdown tiếng Việt, ngắn gọn, rõ ràng, bám sát dữ liệu được cung cấp. '
        'Chỉ trả về markdown, không trả về JSON, không code block. '
        'Rubric chấm theo 4 tiêu chí (in-class, PERFORMANCE EVALUATION): '
        'A. Proficiency — Needs Improvement: ≥1 dấu hiệu: chưa nắm nền tảng/làm đúng khi có gợi ý nhiều/lặp lại lỗi sai; '
        'Meets Expectation: đạt mức cơ bản, không có dấu hiệu Needs Improvement; '
        'Exceeds Expectation: ≥1 dấu hiệu: vượt mục tiêu bài học/vận dụng sang bài tương tự/tự giải thích được "vì sao". '
        'B. Capacity — Needs Improvement: ≥1 dấu hiệu: bắt nhịp chậm/cần nhắc lại nhiều lần/thường chưa kịp tiến độ; '
        'Meets Expectation: ≥1 dấu hiệu: nắm nhanh/hoàn thành sớm và chính xác/có thể làm thêm mở rộng; '
        'KHÔNG được dùng Exceeds Expectation cho tiêu chí này (rubric chưa định nghĩa mức đó). '
        'C. Engagement — Needs Improvement: ≥1 dấu hiệu: tham gia thụ động/ít phản hồi/hầu như im lặng cả buổi; '
        'Meets Expectation: ≥1 dấu hiệu: chủ động phát biểu/phản hồi nhanh/tích cực đặt câu hỏi hoặc đóng góp; '
        'KHÔNG được dùng Exceeds Expectation cho tiêu chí này (rubric chưa định nghĩa mức đó). '
        'LƯU Ý ENGAGEMENT: Rubric yêu cầu quan sát trực tiếp (giơ tay, đặt câu hỏi). '
        'LMS chỉ cung cấp speakingTurnCount — đây là proxy gián tiếp. '
        'Khi chỉ có speakingTurnCount, bắt buộc ghi "Độ tin cậy kết luận: Thấp–Trung bình" và nêu cần giáo viên quan sát thêm. '
        'D. Self-regulation — Needs Improvement: ≥1 dấu hiệu: cần nhắc để bắt đầu bài/mất tập trung/dễ bỏ task hoặc bỏ trống; '
        'Meets Expectation: ≥1 dấu hiệu: chủ động vào task không cần nhắc/duy trì tập trung tốt/linh hoạt khi gặp bài khó không bỏ trống; '
        'KHÔNG được dùng Exceeds Expectation cho tiêu chí này (rubric chưa định nghĩa mức đó). '
        'LƯU Ý SELF-REGULATION: Toàn bộ chỉ số rubric yêu cầu quan sát trực tiếp của giáo viên. '
        'LMS không có signal trực tiếp cho tiêu chí này — chỉ có teacherComment, sessionSummary và completion làm proxy. '
        'Khi thiếu teacherComment/sessionSummary, bắt buộc ghi "Độ tin cậy kết luận: Thấp" và khuyến nghị GV ghi chú sau buổi. '
        'Điểm số 0–100 ánh xạ: Needs Improvement 0–39, Meets Expectation 40–79, Exceeds Expectation 80–100 chỉ dùng cho Proficiency '
        '(Capacity/Engagement/Self-regulation: Needs Improvement 0–39, Meets Expectation 40–100). '
        '(Chọn điểm cụ thể trong khoảng dựa trên mức độ bằng chứng.) '
        'Sử dụng heading và bullet list theo cấu trúc sau (ĐÚNG THỨ TỰ NÀY): '
        '# Nhận xét buổi học - <lesson_label>; '
        '## Tổng quan; '
        '## So sánh buổi gần đây; '
        '## Dữ liệu nền (nghe – nói – đọc); '
        '## Điểm mạnh; '
        '## Ưu tiên cải thiện; '
        '## Đánh giá 4 tiêu chí in-class; '
        '## Kế hoạch buổi sau; '
        '## Lời nhắn phụ huynh. '
        '(Lưu ý: "Đánh giá 4 tiêu chí" phải đứng TRƯỚC "Kế hoạch buổi sau" để kế hoạch bám sát kết quả rubric.) '
        'Dữ liệu đầu vào có thể gồm current_lesson_data, lesson_progress_context (recent_lessons tối đa 2 buổi gần nhất), '
        'lesson_skill_context (tổng hợp từ moments), và rubric_data_quality (độ phủ dữ liệu do hệ thống tính: '
        'skill_pillars + rubric_criteria với system_confidence low|medium|high). '
        'Bắt buộc căn cứ rubric_data_quality khi viết Độ tin cậy kết luận và Cách củng cố đánh giá; không mâu thuẫn '
        '(ví dụ hệ thống low mà lại ghi Cao nếu không giải thích rõ nguồn bổ sung ngoài log). '
        'Nếu lesson_progress_context.progress_context.is_first_lesson=true hoặc thiếu dữ liệu thời gian, '
        'hãy coi đây là buổi học đầu tiên, KHÔNG suy diễn tiến bộ theo lịch sử, và ghi rõ "chưa đủ dữ liệu" ở phần cần so sánh. '
        'Nếu có recent_lessons, bắt buộc có bullet bắt đầu bằng "- So sánh buổi gần đây: " trong mục "## So sánh buổi gần đây". '
        'Nếu recent_lessons có 2 buổi thì bullet này phải nhắc rõ cả 2 lesson_id; nếu có 1 buổi thì phải nhắc rõ lesson_id của buổi đó. '
        'Nội dung so sánh phải nêu điểm tiến bộ/khác biệt gần đây và chỉ dựa trên dữ liệu thực tế. '
        'Khi so sánh, ưu tiên nhắc rõ nội dung học giữa các buổi: script_name/chủ đề, target vocabulary, target grammar, '
        'và từ/cấu trúc còn yếu lặp lại (nếu có). Không chỉ nêu số liệu chung chung. '
        'Trong "## Dữ liệu nền (nghe – nói – đọc)", bắt buộc có đúng 3 bullet chính theo thứ tự: '
        '1) "- Nghe:"; 2) "- Nói:"; 3) "- Đọc:". '
        'Mỗi bullet chính có 3 bullet con: '
        '"  - Làm được: ..." (điểm số cao, ví dụ đúng, phát âm tốt), '
        '"  - Còn hạn chế: ..." (điểm số trung bình, lỗi lặp lại, cần hỗ trợ), '
        '"  - Chưa có dữ liệu: ..." (không có log hoặc attempt_count=0 cho loại này). '
        'Khi không có bằng chứng cho một dòng: ghi "chưa đủ dữ liệu", không bịa. '
        'Nghe dựa trên lesson_skill_context.listening_quiz; '
        'Nói tổng hợp speaking_pronunciation_vocab và speaking_sentence_length_by_activity; '
        'Đọc dựa trên lesson_skill_context.reading_fluency. '
        'Nếu data_coverage = false hoặc thiếu bằng chứng, ghi "chưa đủ dữ liệu" trong bullet tương ứng. '
        'QUY TẮC ĐỘ TIN CẬY (bắt buộc khi dữ liệu không đủ để kết luận chắc chắn): '
        'Với từng mục Nghe / Nói / Đọc trong "## Dữ liệu nền", nếu thiếu dữ liệu hoặc mẫu quá ít (attempt_count thấp, evidence trống, chỉ suy luận gián tiếp), '
        'sau 3 dòng "Tốt / Chưa tốt / Yếu" phải thêm đúng 2 bullet con thụt 2 dấu cách: '
        '"  - Độ tin cậy kết luận: ..." (mức Thấp / Trung bình / Cao hoặc ước lượng % 0–100, kèm 1 câu vì sao chưa chắc) '
        'và "  - Cách củng cố đánh giá: ..." (giải pháp cụ thể: cần thêm hoạt động/loại bài gì, quan sát gì ở buổi sau để chấm đúng mục đó). '
        'Trong "## Đánh giá 4 tiêu chí in-class", bắt buộc đủ 4 tiêu chí theo thứ tự A->D, mỗi tiêu chí 1 bullet cha trên 1 dòng: '
        '- A. Proficiency – Năng lực kiến thức & vận dụng; '
        '- B. Capacity – Năng lực tiếp thu & tiến độ; '
        '- C. Engagement – Tham gia & tương tác; '
        '- D. Self-regulation – Tự điều chỉnh & quản lý học tập. '
        'Quy tắc markdown: giữa các tiêu chí cách 1 dòng trống; mỗi tiêu chí có đúng 4 bullet con thụt 2 dấu cách theo thứ tự: '
        '"  - Đo lường: ...", "  - Kết quả hiện tại: ...", "  - Nhận xét: ...", "  - Khuyến nghị: ...". '
        'Dòng "Đo lường" nêu chỉ số/bằng chứng từ dữ liệu (kể cả stats, moments, từ/ngữ pháp yếu); '
        'dòng "Kết quả hiện tại" bắt buộc ghi mức rubric phù hợp: Proficiency dùng được cả 3 mức; '
        'Capacity/Engagement/Self-regulation chỉ dùng Needs Improvement hoặc Meets Expectation (không dùng Exceeds Expectation); '
        'có thể kèm điểm 0–100 hoặc mô tả ngắn bám rubric; '
        'dòng "Nhận xét" bám bằng chứng; dòng "Khuyến nghị" hành động cụ thể. '
        'Nếu với một tiêu chí dữ liệu hệ thống không đủ tin cậy để xếp rubric chắc chắn, sau 4 bullet trên (cùng tiêu chí đó) '
        'bắt buộc thêm 2 bullet con: "  - Độ tin cậy kết luận: ..." và "  - Cách củng cố đánh giá: ..." với nội dung như quy tắc phần Dữ liệu nền. '
        'Khi rubric_data_quality hoặc data_coverage cho thấy thiếu/thưa, phải có đủ 2 bullet Độ tin cậy + Cách củng cố. '
        'Khi hệ thống system_confidence=high cho tiêu chí đó, có thể ghi ngắn "Độ tin cậy kết luận: Cao (đồng thuận với hệ thống)" '
        'hoặc lược bớt Cách củng cố nếu không cần thiết. '
        'Không dùng "|" để nối nhiều nhãn trên một dòng trong section này. '
        'Không thêm section kế hoạch 2 tuần. '
        'Nếu dữ liệu thiếu, vẫn xuất đủ 4 tiêu chí, ghi rõ "chưa đủ dữ liệu" và áp dụng đầy đủ quy tắc Độ tin cậy / Cách củng cố đánh giá.'
    )
    user_payload = {
        'lesson_label': lesson_label or 'Lesson',
        'lesson_input': lesson_input,
    }
    return [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
    ]


def _build_portfolio_feedback_messages(
    lessons_payload: list[dict[str, str]],
    portfolio_label: str | None,
    portfolio_rubric_per_lesson: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    context = _build_portfolio_input_context(lessons_payload)
    system_prompt = (
        'Bạn là giáo viên tiếng Anh tiểu học có kinh nghiệm, giỏi tổng hợp tiến trình học theo nhiều buổi. '
        'Nhiệm vụ: viết nhận xét tổng hợp bằng markdown tiếng Việt, thân thiện, dễ hiểu với phụ huynh. '
        'Chỉ trả về markdown, không JSON, không code block. '
        'Rubric chấm theo 4 tiêu chí in-class: '
        'A. Proficiency (3 mức — NI 0–39, ME 40–79, EE 80–100): '
        'NI: chưa nắm nền tảng/lặp lại lỗi sai; ME: đạt cơ bản không có NI; EE: vượt mục tiêu/tự giải thích được. '
        'B. Capacity (2 mức — NI 0–39, ME 40–100; KHÔNG dùng Exceeds Expectation): '
        'NI: bắt nhịp chậm/cần nhắc lại nhiều lần/thường chưa kịp tiến độ; ME: nắm nhanh/hoàn thành sớm và chính xác. '
        'C. Engagement (2 mức — NI 0–39, ME 40–100; KHÔNG dùng Exceeds Expectation): '
        'NI: tham gia thụ động/ít phản hồi; ME: chủ động phát biểu/phản hồi nhanh/đặt câu hỏi. '
        'LMS chỉ có speakingTurnCount (proxy gián tiếp) — rubric đòi quan sát trực tiếp. '
        'D. Self-regulation (2 mức — NI 0–39, ME 40–100; KHÔNG dùng Exceeds Expectation): '
        'NI: cần nhắc để bắt đầu/mất tập trung/dễ bỏ task; ME: chủ động vào task/duy trì tập trung. '
        'LMS không có signal trực tiếp — chỉ có teacherComment/sessionSummary/completion làm proxy. '
        'Sử dụng heading và bullet list theo cấu trúc sau: '
        '# Nhận xét chung quá trình học; '
        '## Tổng quan quá trình; '
        '## Xu hướng tiến bộ; '
        '## Xu hướng theo 4 tiêu chí; '
        '## Phong cách học hiện tại; '
        '## Điểm mạnh; '
        '## Ưu tiên can thiệp; '
        '## Đánh giá 4 tiêu chí in-class; '
        '## Kế hoạch 2 tuần; '
        '## Lời nhắn phụ huynh. '
        'Yêu cầu chi tiết theo section: '
        '1) "Tổng quan quá trình": nêu mức độ tiến bộ chung, độ ổn định và mức hoàn thành theo toàn bộ các buổi. '
        '2) "Xu hướng tiến bộ": nêu chiều hướng tăng/giảm/dao động theo thời gian và chỉ ra giai đoạn rõ ràng (đầu kỳ, gần đây). '
        '3) "Xu hướng theo 4 tiêu chí": với Proficiency, Capacity, Engagement, Self-regulation — mỗi tiêu chí 1–2 bullet, có bằng chứng từ portfolio_context; '
        'nếu số buổi có dữ liệu ít hoặc chỉ số thưa, thêm ngay trong bullet đó "Độ tin cậy kết luận: ..." và "Cách củng cố đánh giá: ..." (mức Thấp/Trung bình/Cao hoặc %, + việc cần làm để tăng độ tin cậy). '
        '4) "Phong cách học hiện tại": mô tả chủ động, phản xạ, tập trung, tiếp thu dựa trên dữ liệu. '
        '5) "Đánh giá 4 tiêu chí in-class": đủ A->D (Proficiency, Capacity, Engagement, Self-regulation), '
        'mỗi tiêu chí 1 bullet cha, dưới đó 4 bullet con: Đo lường; Kết quả hiện tại (Proficiency: 1 trong 3 mức; Capacity/Engagement/Self-regulation: chỉ Needs Improvement hoặc Meets Expectation + có thể kèm điểm); '
        'Nhận xét; Khuyến nghị. Cách nhau 1 dòng trống giữa các tiêu chí. '
        'Khi tổng hợp nhiều buổi mà dữ liệu không đủ tin cậy cho một tiêu chí, sau 4 bullet con bắt buộc thêm '
        '"  - Độ tin cậy kết luận: ..." và "  - Cách củng cố đánh giá: ..." (hành động cụ thể để thu thập/quan sát thêm). '
        '6) "Kế hoạch 2 tuần": 6-8 hành động cụ thể, mỗi hành động ghi tần suất/tuần + thời lượng + 1-2 tiêu chí rubric liên quan, '
        'bám sát "Đánh giá 4 tiêu chí in-class". '
        '7) "Lời nhắn phụ huynh": khuyến nghị ngắn gọn, khả thi tại nhà. '
        'Quy tắc trình bày: mỗi ý bắt đầu bằng "- "; mỗi section cách nhau 1 dòng trống. '
        'Mọi nhận định bám dữ liệu; thiếu dữ liệu thì ghi "chưa đủ dữ liệu" và luôn kèm Độ tin cậy kết luận + Cách củng cố đánh giá cho phần đó. '
        'Nếu user payload có portfolio_rubric_data_quality.per_lesson, mỗi phần tử chứa rubric_data_quality cho một buổi — '
        'bắt buộc dùng system_confidence/reason để nhất quán khi viết xu hướng và đánh giá 4 tiêu chí; không mâu thuẫn với hệ thống.'
    )
    user_payload: dict[str, Any] = {
        'portfolio_label': portfolio_label or 'Tong hop qua trinh hoc',
        'total_lessons': len(lessons_payload),
        'portfolio_context': context,
    }
    if portfolio_rubric_per_lesson:
        user_payload['portfolio_rubric_data_quality'] = {'per_lesson': portfolio_rubric_per_lesson}
    return [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
    ]


def _normalize_lesson_feedback_payload(parsed: dict[str, Any], lesson_label: str | None = None) -> dict[str, Any]:
    breakdown = parsed.get('session_breakdown')
    if not isinstance(breakdown, dict):
        breakdown = {}

    next_lesson_plan = parsed.get('next_lesson_plan')
    if not isinstance(next_lesson_plan, list):
        next_lesson_plan = []
    normalized_plan: list[dict[str, Any]] = []
    for item in next_lesson_plan:
        source = item if isinstance(item, dict) else {}
        normalized_plan.append(
            {
                'step': _normalize_text(source.get('step')),
                'duration_minutes': _normalize_score(source.get('duration_minutes')),
            }
        )

    priority_improvements = parsed.get('priority_improvements')
    if not isinstance(priority_improvements, list):
        priority_improvements = []
    normalized_priorities: list[dict[str, str]] = []
    for item in priority_improvements[:3]:
        normalized = _normalize_priority_item(item)
        if normalized is not None:
            normalized_priorities.append(normalized)

    if not normalized_plan:
        normalized_plan = _build_fallback_next_lesson_plan(normalized_priorities)

    return {
        'lesson_label': _normalize_text(parsed.get('lesson_label'), fallback=lesson_label or 'Lesson'),
        'teacher_tone': _normalize_text(parsed.get('teacher_tone'), fallback='warm_encouraging'),
        'overall_comment': _normalize_text(parsed.get('overall_comment')),
        'session_breakdown': {
            'proficiency': _normalize_session_criterion(breakdown.get('proficiency')),
            'capacity': _normalize_session_criterion(breakdown.get('capacity')),
            'engagement': _normalize_session_criterion(breakdown.get('engagement')),
            'self_regulation': _normalize_session_criterion(breakdown.get('self_regulation')),
        },
        'strengths': _normalize_string_list(parsed.get('strengths')),
        'priority_improvements': normalized_priorities,
        'next_lesson_plan': normalized_plan,
        'parent_message': _normalize_text(parsed.get('parent_message')),
    }


def _normalize_portfolio_feedback_payload(
    parsed: dict[str, Any], lessons_payload: list[dict[str, str]], portfolio_label: str | None = None
) -> dict[str, Any]:
    skill_trends = parsed.get('skill_trends')
    if not isinstance(skill_trends, dict):
        skill_trends = {}

    top_priorities = parsed.get('top_priorities')
    if not isinstance(top_priorities, list):
        top_priorities = []
    normalized_priorities: list[dict[str, str]] = []
    for item in top_priorities[:3]:
        normalized = _normalize_portfolio_priority_item(item)
        if normalized is not None:
            normalized_priorities.append(normalized)

    study_plan = parsed.get('study_plan_2_weeks')
    if not isinstance(study_plan, list):
        study_plan = []
    normalized_plan = [_normalize_study_plan_item(item) for item in study_plan]

    strengths = _normalize_string_list(parsed.get('top_strengths'))

    payload = {
        'portfolio_label': _normalize_text(parsed.get('portfolio_label'), fallback=portfolio_label or 'Tong hop qua trinh hoc'),
        'total_lessons': _normalize_score(parsed.get('total_lessons')) or len(lessons_payload),
        'date_range': _normalize_date_range(parsed.get('date_range')),
        'overall_assessment': _normalize_text(parsed.get('overall_assessment'), fallback=''),
        'skill_trends': {
            'proficiency': _normalize_skill_trend(skill_trends.get('proficiency')),
            'capacity': _normalize_skill_trend(skill_trends.get('capacity')),
            'engagement': _normalize_skill_trend(skill_trends.get('engagement')),
            'self_regulation': _normalize_skill_trend(skill_trends.get('self_regulation')),
        },
        'top_strengths': strengths,
        'top_priorities': normalized_priorities,
        'study_plan_2_weeks': normalized_plan,
        'parent_message': _normalize_text(parsed.get('parent_message'), fallback=''),
    }
    return payload


def generate_lesson_feedback(report_text: str, lesson_label: str | None = None) -> str:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')

    completion = client.chat.completions.create(
        model=model,
        messages=_build_lesson_feedback_messages(report_text, lesson_label),
        temperature=0.2,
    )

    content = completion.choices[0].message.content
    markdown = (content or '').strip()
    if not markdown:
        raise ValueError('LLM returned an empty response')
    return markdown


def stream_lesson_feedback(report_text: str, lesson_label: str | None = None):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    stream = client.chat.completions.create(
        model=model,
        messages=_build_lesson_feedback_messages(report_text, lesson_label),
        temperature=0.2,
        stream=True,
    )

    yield {'type': 'status', 'message': 'Dang phan tich du lieu buoi hoc...'}
    has_content = False
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if not delta:
            continue
        has_content = True
        yield {'type': 'chunk', 'content': delta}
    if not has_content:
        raise ValueError('LLM returned an empty response')


def generate_portfolio_feedback(
    lessons_payload: list[dict[str, str]],
    portfolio_label: str | None = None,
    portfolio_rubric_per_lesson: list[dict[str, Any]] | None = None,
) -> str:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')

    completion = client.chat.completions.create(
        model=model,
        messages=_build_portfolio_feedback_messages(
            lessons_payload, portfolio_label, portfolio_rubric_per_lesson=portfolio_rubric_per_lesson
        ),
        temperature=0.2,
    )
    content = completion.choices[0].message.content
    markdown = (content or '').strip()
    if not markdown:
        raise ValueError('LLM returned an empty response')
    return markdown


def stream_portfolio_feedback(
    lessons_payload: list[dict[str, str]],
    portfolio_label: str | None = None,
    portfolio_rubric_per_lesson: list[dict[str, Any]] | None = None,
):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    stream = client.chat.completions.create(
        model=model,
        messages=_build_portfolio_feedback_messages(
            lessons_payload, portfolio_label, portfolio_rubric_per_lesson=portfolio_rubric_per_lesson
        ),
        temperature=0.2,
        stream=True,
    )

    yield {'type': 'status', 'message': 'Dang phan tich tong hop tat ca buoi hoc...'}
    has_content = False
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if not delta:
            continue
        has_content = True
        yield {'type': 'chunk', 'content': delta}
    if not has_content:
        raise ValueError('LLM returned an empty response')
