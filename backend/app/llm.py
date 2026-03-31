import json
import os
from typing import Any

from openai import OpenAI

VALID_PRIORITY_SKILLS = {'pronunciation', 'vocabulary', 'grammar', 'reaction_confidence', 'participation'}
VALID_PRIORITIES = {'high', 'medium', 'low'}


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


def _build_fallback_next_lesson_plan(priorities: list[dict[str, str]]) -> list[dict[str, Any]]:
    default_by_skill = {
        'pronunciation': {'step': 'Luyen phat am theo cum tu kho voi shadowing', 'duration_minutes': 12},
        'grammar': {'step': 'On mau cau trong tam va dat cau theo tinh huong', 'duration_minutes': 10},
        'vocabulary': {'step': 'On tu vung trong bai bang flashcard va dat cau', 'duration_minutes': 10},
        'reaction_confidence': {'step': 'Luyen hoi dap nhanh theo tinh huong gan gui', 'duration_minutes': 8},
        'participation': {'step': 'Khuyen khich be noi thanh cau day du trong moi luot', 'duration_minutes': 8},
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
    system_prompt = (
        'Ban la giao vien tieng Anh tieu hoc nhieu kinh nghiem, giong dieu am ap va khich le, '
        'nhung phan tich phai sau va co tinh chuyen mon. '
        'Nhiem vu: viet nhan xet chi tiet cho 1 buoi hoc dua tren du lieu lesson duoc cung cap. '
        'Chi tra ve JSON hop le, khong markdown, khong van ban ngoai JSON. '
        'Moi nhan xet phai bam sat du lieu dau vao, khong suy dien. '
        'Neu thieu du lieu cho mot y, ghi ro "chua du du lieu". '
        'Voi moi ky nang, can neu: hien trang, bang chung du lieu, anh huong den hoc tap, '
        'va hanh dong cai thien cu the. '
        'Phan tich can so sanh duoc diem manh va diem can cai thien giua pronunciation, vocabulary, grammar, '
        'participation, reaction_confidence; neu co the hay chi ra mau loi lap lai va muc do on dinh/dao dong. '
        'overall_comment phai dai 6-10 cau. '
        'Moi comment trong session_breakdown phai chi tiet toi thieu 4 cau. '
        'strengths can it nhat 3 y cu the. '
        'priority_improvements toi da 3 muc, sap xep theo uu tien, '
        'moi muc can co muc tieu do duoc cho buoi sau. '
        'Chi duoc dung skill trong [pronunciation, vocabulary, grammar, reaction_confidence, participation] '
        'va priority trong [high, medium, low]. '
        'Output bat buoc co cac truong: lesson_label, teacher_tone, overall_comment, '
        'session_breakdown(participation, pronunciation, vocabulary, grammar, reaction_confidence), '
        'strengths, priority_improvements, next_lesson_plan, parent_message. '
        'Moi muc trong session_breakdown co score(0-100), comment, evidence(array string). '
        'parent_message phai 4-6 cau, tich cuc va co huong dan phu huynh dong hanh. '
        'Rang buoc bat buoc cho next_lesson_plan: '
        '1) Luon la array dung 3 phan tu, khong duoc rong. '
        '2) Moi phan tu la object co day du 2 khoa: step (string), duration_minutes (integer). '
        '3) duration_minutes trong khoang 5-20 va tong 3 muc trong khoang 25-35 phut. '
        '4) Noi dung phai lien ket truc tiep voi priority_improvements; neu thieu du lieu van phai de xuat ke hoach cu the, khong duoc de [] hay null. '
        '5) Truoc khi tra ve, tu kiem tra lai JSON hop le va next_lesson_plan da dung 3 muc.'
    )
    user_payload = {
        'lesson_label': lesson_label or 'Lesson',
        'lesson_data': report_text,
        'output_contract': {
            'next_lesson_plan_required_shape': [
                {'step': 'Mo ta hanh dong cu the cho buoi sau', 'duration_minutes': 10},
                {'step': 'Mo ta hanh dong cu the cho buoi sau', 'duration_minutes': 10},
                {'step': 'Mo ta hanh dong cu the cho buoi sau', 'duration_minutes': 10},
            ]
        },
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
            'participation': _normalize_session_criterion(breakdown.get('participation')),
            'pronunciation': _normalize_session_criterion(breakdown.get('pronunciation')),
            'vocabulary': _normalize_session_criterion(breakdown.get('vocabulary')),
            'grammar': _normalize_session_criterion(breakdown.get('grammar')),
            'reaction_confidence': _normalize_session_criterion(breakdown.get('reaction_confidence')),
        },
        'strengths': _normalize_string_list(parsed.get('strengths')),
        'priority_improvements': normalized_priorities,
        'next_lesson_plan': normalized_plan,
        'parent_message': _normalize_text(parsed.get('parent_message')),
    }


def generate_lesson_feedback(report_text: str, lesson_label: str | None = None) -> dict[str, Any]:
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')

    completion = client.chat.completions.create(
        model=model,
        response_format={'type': 'json_object'},
        messages=_build_lesson_feedback_messages(report_text, lesson_label),
        temperature=0.2,
    )

    content = completion.choices[0].message.content
    if not content:
        raise ValueError('LLM returned an empty response')

    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError('LLM output is not a JSON object')

    return _normalize_lesson_feedback_payload(parsed, lesson_label)


def stream_lesson_feedback(report_text: str, lesson_label: str | None = None):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is missing')

    client = OpenAI(api_key=api_key)
    model = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
    stream = client.chat.completions.create(
        model=model,
        response_format={'type': 'json_object'},
        messages=_build_lesson_feedback_messages(report_text, lesson_label),
        temperature=0.2,
        stream=True,
    )

    yield {'type': 'status', 'message': 'Dang phan tich du lieu buoi hoc...'}
    chunks: list[str] = []
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if not delta:
            continue
        chunks.append(delta)
        yield {'type': 'chunk', 'content': delta}

    content = ''.join(chunks).strip()
    if not content:
        raise ValueError('LLM returned an empty response')
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError('LLM output is not a JSON object')
    yield {'type': 'result', 'data': _normalize_lesson_feedback_payload(parsed, lesson_label)}
