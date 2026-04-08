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
        'Proficiency (nắm kiến thức, giải thích, vận dụng nhẹ), '
        'Capacity (tiếp thu, xử lý bài, tiến độ), '
        'Engagement (tham gia, phản hồi, chủ động), '
        'Self-regulation (tự duy trì, tự kiểm tra, tự điều chỉnh, quản lý thời gian). '
        'Mỗi tiêu chí xếp một trong 3 mức rubric (ghi rõ trong "Kết quả hiện tại"): '
        '⚠️ Needs Improvement (cần cải thiện), '
        '✅ Meets Expectation (đạt kỳ vọng), '
        '🌟 Exceeds Expectation (vượt kỳ vọng). '
        'Điểm số 0–100 ánh xạ: Needs Improvement 0–39, Meets Expectation 40–79, Exceeds Expectation 80–100 '
        '(chọn điểm cụ thể trong khoảng dựa trên mức độ bằng chứng). '
        'Sử dụng heading và bullet list theo cấu trúc sau: '
        '# Nhận xét buổi học - <lesson_label>; '
        '## Tổng quan; '
        '## So sánh buổi gần đây; '
        '## Dữ liệu nền (nghe – nói – đọc); '
        '## Điểm mạnh; '
        '## Ưu tiên cải thiện; '
        '## Kế hoạch buổi sau; '
        '## Đánh giá 4 tiêu chí in-class; '
        '## Lời nhắn phụ huynh. '
        'Dữ liệu đầu vào có thể gồm current_lesson_data, lesson_progress_context (recent_lessons tối đa 2 buổi gần nhất), '
        'và lesson_skill_context (tổng hợp từ moments). '
        'Nếu lesson_progress_context.progress_context.is_first_lesson=true hoặc thiếu dữ liệu thời gian, '
        'hãy coi đây là buổi học đầu tiên, KHÔNG suy diễn tiến bộ theo lịch sử, và ghi rõ "chưa đủ dữ liệu" ở phần cần so sánh. '
        'Nếu có recent_lessons, bắt buộc có bullet bắt đầu bằng "- So sánh buổi gần đây: " trong mục "## So sánh buổi gần đây". '
        'Nếu recent_lessons có 2 buổi thì bullet này phải nhắc rõ cả 2 lesson_id; nếu có 1 buổi thì phải nhắc rõ lesson_id của buổi đó. '
        'Nội dung so sánh phải nêu điểm tiến bộ/khác biệt gần đây và chỉ dựa trên dữ liệu thực tế. '
        'Khi so sánh, ưu tiên nhắc rõ nội dung học giữa các buổi: script_name/chủ đề, target vocabulary, target grammar, '
        'và từ/cấu trúc còn yếu lặp lại (nếu có). Không chỉ nêu số liệu chung chung. '
        'Trong "## Dữ liệu nền (nghe – nói – đọc)", bắt buộc có đúng 3 bullet chính theo thứ tự: '
        '1) "- Nghe:"; 2) "- Nói:"; 3) "- Đọc:". '
        'Mỗi bullet chính có 3 bullet con: "  - Tốt: ...", "  - Chưa tốt: ...", "  - Yếu: ...". '
        'Nghe dựa trên lesson_skill_context.listening_quiz; '
        'Nói tổng hợp speaking_pronunciation_vocab và speaking_sentence_length_by_activity; '
        'Đọc dựa trên lesson_skill_context.reading_fluency. '
        'Nếu data_coverage = false hoặc thiếu bằng chứng, ghi "chưa đủ dữ liệu" trong bullet tương ứng. '
        'Trong "## Đánh giá 4 tiêu chí in-class", bắt buộc đủ 4 tiêu chí theo thứ tự A->D, mỗi tiêu chí 1 bullet cha trên 1 dòng: '
        '- A. Proficiency – Năng lực kiến thức & vận dụng; '
        '- B. Capacity – Năng lực tiếp thu & tiến độ; '
        '- C. Engagement – Tham gia & tương tác; '
        '- D. Self-regulation – Tự điều chỉnh & quản lý học tập. '
        'Quy tắc markdown: giữa các tiêu chí cách 1 dòng trống; mỗi tiêu chí có đúng 4 bullet con thụt 2 dấu cách theo thứ tự: '
        '"  - Đo lường: ...", "  - Kết quả hiện tại: ...", "  - Nhận xét: ...", "  - Khuyến nghị: ...". '
        'Dòng "Đo lường" nêu chỉ số/bằng chứng từ dữ liệu (kể cả stats, moments, từ/ngữ pháp yếu); '
        'dòng "Kết quả hiện tại" bắt buộc ghi một trong ba mức rubric (Needs Improvement / Meets Expectation / Exceeds Expectation) '
        'và có thể kèm điểm 0–100 hoặc mô tả ngắn bám rubric; '
        'dòng "Nhận xét" bám bằng chứng; dòng "Khuyến nghị" hành động cụ thể. '
        'Không dùng "|" để nối nhiều nhãn trên một dòng trong section này. '
        'Không thêm section kế hoạch 2 tuần. '
        'Nếu dữ liệu thiếu, vẫn xuất đủ 4 tiêu chí và ghi rõ "chưa đủ dữ liệu" ở phần tương ứng.'
    )
    user_payload = {
        'lesson_label': lesson_label or 'Lesson',
        'lesson_input': lesson_input,
        'format': 'markdown',
    }
    return [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
    ]


def _build_portfolio_feedback_messages(
    lessons_payload: list[dict[str, str]], portfolio_label: str | None
) -> list[dict[str, str]]:
    context = _build_portfolio_input_context(lessons_payload)
    system_prompt = (
        'Bạn là giáo viên tiếng Anh tiểu học có kinh nghiệm, giỏi tổng hợp tiến trình học theo nhiều buổi. '
        'Nhiệm vụ: viết nhận xét tổng hợp bằng markdown tiếng Việt, thân thiện, dễ hiểu với phụ huynh. '
        'Chỉ trả về markdown, không JSON, không code block. '
        'Rubric chấm theo 4 tiêu chí in-class: Proficiency, Capacity, Engagement, Self-regulation; '
        'mỗi tiêu chí một trong ba mức: Needs Improvement, Meets Expectation, Exceeds Expectation '
        '(điểm 0–100: Needs Improvement 0–39, Meets 40–79, Exceeds 80–100). '
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
        '3) "Xu hướng theo 4 tiêu chí": với Proficiency, Capacity, Engagement, Self-regulation — mỗi tiêu chí 1–2 bullet, có bằng chứng từ portfolio_context. '
        '4) "Phong cách học hiện tại": mô tả chủ động, phản xạ, tập trung, tiếp thu dựa trên dữ liệu. '
        '5) "Đánh giá 4 tiêu chí in-class": đủ A->D (Proficiency, Capacity, Engagement, Self-regulation), '
        'mỗi tiêu chí 1 bullet cha, dưới đó 4 bullet con: Đo lường; Kết quả hiện tại (bắt buộc một trong ba mức rubric + có thể kèm điểm); '
        'Nhận xét; Khuyến nghị. Cách nhau 1 dòng trống giữa các tiêu chí. '
        '6) "Kế hoạch 2 tuần": 6-8 hành động cụ thể, mỗi hành động ghi tần suất/tuần + thời lượng + 1-2 tiêu chí rubric liên quan, '
        'bám sát "Đánh giá 4 tiêu chí in-class". '
        '7) "Lời nhắn phụ huynh": khuyến nghị ngắn gọn, khả thi tại nhà. '
        'Quy tắc trình bày: mỗi ý bắt đầu bằng "- "; mỗi section cách nhau 1 dòng trống. '
        'Mọi nhận định bám dữ liệu; thiếu dữ liệu thì ghi "chưa đủ dữ liệu".'
    )
    user_payload = {
        'portfolio_label': portfolio_label or 'Tong hop qua trinh hoc',
        'total_lessons': len(lessons_payload),
        'portfolio_context': context,
        'format': 'markdown',
    }
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
    lessons_payload: list[dict[str, str]], portfolio_label: str | None = None
) -> str:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')

    completion = client.chat.completions.create(
        model=model,
        messages=_build_portfolio_feedback_messages(lessons_payload, portfolio_label),
        temperature=0.2,
    )
    content = completion.choices[0].message.content
    markdown = (content or '').strip()
    if not markdown:
        raise ValueError('LLM returned an empty response')
    return markdown


def stream_portfolio_feedback(lessons_payload: list[dict[str, str]], portfolio_label: str | None = None):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    stream = client.chat.completions.create(
        model=model,
        messages=_build_portfolio_feedback_messages(lessons_payload, portfolio_label),
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
