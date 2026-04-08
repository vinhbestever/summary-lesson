"""
System-side assessment of data sufficiency for in-class rubric and skill pillars.
Used to enrich LLM input and to append a guaranteed markdown appendix.
"""

from __future__ import annotations

from typing import Any


def _as_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _confidence_from_count(count: int, low_lt: int = 2, medium_lt: int = 5) -> str:
    if count >= medium_lt:
        return 'high'
    if count >= low_lt:
        return 'medium'
    return 'low'


def _listening_remediation(n: int) -> str:
    if n == 0:
        return (
            'Bổ sung ít nhất 3–5 câu listening (single_choice/matching) có chấm điểm trong buổi sau; '
            'lưu đề bài/tình huống để đối chiếu với transcript.'
        )
    if n < 3:
        return (
            'Tăng số lượt listening có điểm (mục tiêu ≥5 lượt/buổi) và xen kẽ độ khó để ước lượng ổn định hơn.'
        )
    return 'Duy trì tần suất tương tự; có thể thêm 1–2 câu matching để kiểm tra chi tiết.'


def _speaking_remediation(n: int) -> str:
    if n == 0:
        return (
            'Thêm hoạt động nói có transcript kỳ vọng (từ/cụm/câu) và lưu userTranscript + score; '
            'ưu tiên cả game_pronunciation và speaking_scripted.'
        )
    if n < 3:
        return (
            'Tăng số lượt nói được log (mục tiêu ≥5), gồm cả câu ngắn và câu dài để tách Proficiency theo độ dài.'
        )
    return 'Giữ đủ loại hoạt động; ghi nhận thêm lỗi lặp lại (từ/cấu trúc) nếu LMS hỗ trợ.'


def _reading_remediation(n: int) -> str:
    if n == 0:
        return (
            'Thêm ít nhất 2–3 lượt đọc to/read-aloud có điểm (dialogue, conversation hoặc speaking_scripted dài).'
        )
    if n < 2:
        return 'Tăng lên ≥3 lượt đọc có điểm để ước lượng trôi chảy ổn định hơn.'
    return 'Duy trì; có thể thêm đoạn khó hơn một bậc để kiểm tra vận dụng.'


def build_skill_pillar_assessment(skill_ctx: dict[str, Any]) -> dict[str, Any]:
    listening = skill_ctx.get('listening_quiz') if isinstance(skill_ctx.get('listening_quiz'), dict) else {}
    sp_vocab = (
        skill_ctx.get('speaking_pronunciation_vocab')
        if isinstance(skill_ctx.get('speaking_pronunciation_vocab'), dict)
        else {}
    )
    ssl = (
        skill_ctx.get('speaking_sentence_length_by_activity')
        if isinstance(skill_ctx.get('speaking_sentence_length_by_activity'), dict)
        else {}
    )
    reading = skill_ctx.get('reading_fluency') if isinstance(skill_ctx.get('reading_fluency'), dict) else {}

    listen_n = int(listening.get('attempt_count') or 0)
    speak_n = int(sp_vocab.get('attempt_count') or 0) + int(ssl.get('total_attempt_count') or 0)
    read_n = int(reading.get('attempt_count') or 0)

    return {
        'listening': {
            'attempt_count': listen_n,
            'system_confidence': _confidence_from_count(listen_n, 1, 3),
            'remediation_if_low': _listening_remediation(listen_n),
        },
        'speaking': {
            'attempt_count': speak_n,
            'system_confidence': _confidence_from_count(speak_n, 1, 4),
            'remediation_if_low': _speaking_remediation(speak_n),
        },
        'reading': {
            'attempt_count': read_n,
            'system_confidence': _confidence_from_count(read_n, 1, 3),
            'remediation_if_low': _reading_remediation(read_n),
        },
    }


def build_lesson_rubric_signals(skill_ctx: dict[str, Any], lesson_snapshot: dict[str, Any]) -> dict[str, Any]:
    stats = lesson_snapshot.get('stats') if isinstance(lesson_snapshot.get('stats'), dict) else {}
    skill_ev = (
        lesson_snapshot.get('skill_evidence')
        if isinstance(lesson_snapshot.get('skill_evidence'), dict)
        else {}
    )

    vocab_n = int(skill_ev.get('vocabulary_attempt_count') or 0)
    grammar_n = int(skill_ev.get('grammar_attempt_count') or 0)
    pron = stats.get('averagePronunciationScore')
    has_pron = pron is not None

    listening = skill_ctx.get('listening_quiz') if isinstance(skill_ctx.get('listening_quiz'), dict) else {}
    sp_vocab = (
        skill_ctx.get('speaking_pronunciation_vocab')
        if isinstance(skill_ctx.get('speaking_pronunciation_vocab'), dict)
        else {}
    )
    ssl = (
        skill_ctx.get('speaking_sentence_length_by_activity')
        if isinstance(skill_ctx.get('speaking_sentence_length_by_activity'), dict)
        else {}
    )
    reading = skill_ctx.get('reading_fluency') if isinstance(skill_ctx.get('reading_fluency'), dict) else {}

    activity_depth = (
        int(listening.get('attempt_count') or 0)
        + int(sp_vocab.get('attempt_count') or 0)
        + int(ssl.get('total_attempt_count') or 0)
        + int(reading.get('attempt_count') or 0)
    )
    content_signals = vocab_n + grammar_n + (1 if has_pron else 0)

    if activity_depth < 4 or content_signals < 1:
        prof_conf = 'low'
        prof_reason = 'Ít hoạt động có điểm hoặc thiếu dữ liệu từ vựng/ngữ pháp/phát âm.'
    elif activity_depth < 8 or content_signals < 2:
        prof_conf = 'medium'
        prof_reason = 'Dữ liệu vừa đủ gợi ý; cần thêm bằng chứng đa dạng (nghe/nói/đọc + từ-câu).'
    else:
        prof_conf = 'high'
        prof_reason = 'Đủ lượt tương tác có điểm và tín hiệu nội dung.'

    comp = stats.get('sectionsCompletionPercent')
    react = stats.get('averageReactionTimeMs')
    if comp is None and react is None:
        cap_conf, cap_reason = 'low', 'Thiếu % hoàn thành và thời gian phản xạ trung bình.'
    elif comp is None or react is None:
        cap_conf, cap_reason = 'medium', 'Mới có một trong hai chỉ số tiến độ/phản xạ.'
    else:
        cap_conf, cap_reason = 'high', 'Có đủ completion và reaction time để bám tiến độ.'

    turns = _as_int(stats.get('speakingTurnCount'))
    if turns is None:
        eng_conf, eng_reason = 'low', 'Không có speakingTurnCount trong stats.'
    elif turns < 4:
        eng_conf, eng_reason = 'medium', f'Ít lượt nói được log (speakingTurnCount={turns}).'
    else:
        eng_conf, eng_reason = 'high', f'Có đủ lượt nói (speakingTurnCount={turns}) để nhận diện tham gia.'

    teacher = str(stats.get('teacherComment') or '').strip()
    session_s = str(stats.get('sessionSummary') or '').strip()
    qual = bool(teacher or session_s)
    if cap_conf == 'low' and not qual:
        sr_conf, sr_reason = 'low', 'Thiếu chỉ số tiến độ/phản xạ và chưa có ghi chú GV để suy ra tự điều chỉnh.'
    elif cap_conf == 'low' or (not qual and eng_conf != 'high'):
        sr_conf, sr_reason = 'medium', 'Chỉ suy ra một phần từ completion/reaction và/hoặc ghi chú ngắn.'
    else:
        sr_conf, sr_reason = 'high', 'Có chỉ số và/hoặc ghi chú buổi học hỗ trợ suy luận hành vi học.'

    return {
        'proficiency': {
            'system_confidence': prof_conf,
            'reason': prof_reason,
            'metrics': {
                'activity_depth_total_attempts': activity_depth,
                'vocabulary_attempt_count': vocab_n,
                'grammar_attempt_count': grammar_n,
                'has_average_pronunciation_score': has_pron,
            },
        },
        'capacity': {
            'system_confidence': cap_conf,
            'reason': cap_reason,
            'metrics': {
                'sections_completion_percent': comp,
                'average_reaction_time_ms': react,
            },
        },
        'engagement': {
            'system_confidence': eng_conf,
            'reason': eng_reason,
            'metrics': {'speaking_turn_count': turns},
        },
        'self_regulation': {
            'system_confidence': sr_conf,
            'reason': sr_reason,
            'metrics': {'has_teacher_or_session_text': qual},
        },
    }


def build_lesson_rubric_data_quality(skill_ctx: dict[str, Any], lesson_snapshot: dict[str, Any]) -> dict[str, Any]:
    pillars = build_skill_pillar_assessment(skill_ctx)
    rubric = build_lesson_rubric_signals(skill_ctx, lesson_snapshot)
    return {
        'skill_pillars': pillars,
        'rubric_criteria': rubric,
        'note': (
            'system_confidence: low|medium|high — đánh giá độ phủ dữ liệu, không thay thế rubric GV. '
            'Khi low/medium, bắt buộc phản ánh trong nhận xét và phụ lục hệ thống sẽ bổ sung.'
        ),
    }


def format_lesson_appendix_markdown(skill_ctx: dict[str, Any], lesson_snapshot: dict[str, Any]) -> str:
    dq = build_lesson_rubric_data_quality(skill_ctx, lesson_snapshot)
    pillars = dq['skill_pillars']
    rubric = dq['rubric_criteria']

    lines: list[str] = [
        '## Phụ lục (hệ thống): Độ tin cậy dữ liệu & củng cố đánh giá',
        '',
        '_Phần này được tạo tự động từ log buổi học; dùng để bảo đảm không bỏ sót khi dữ liệu mỏng._',
        '',
    ]

    label = {'low': 'Thấp', 'medium': 'Trung bình', 'high': 'Cao'}

    lines.append('### Trụ dữ liệu nền (Nghe – Nói – Đọc)')
    for key, title in (('listening', 'Nghe'), ('speaking', 'Nói'), ('reading', 'Đọc')):
        p = pillars[key]
        conf = p['system_confidence']
        lines.append(f'- **{title}**: độ tin cậy hệ thống — **{label.get(conf, conf)}** '
                     f'({p["attempt_count"]} lượt có điểm).')
        if conf != 'high':
            lines.append(f'  - Cách củng cố: {p["remediation_if_low"]}')
    lines.append('')

    lines.append('### Bốn tiêu chí in-class (theo độ phủ hệ thống)')
    titles = {
        'proficiency': 'Proficiency',
        'capacity': 'Capacity',
        'engagement': 'Engagement',
        'self_regulation': 'Self-regulation',
    }
    for rk, rt in titles.items():
        block = rubric[rk]
        conf = block['system_confidence']
        lines.append(f'- **{rt}**: độ tin cậy hệ thống — **{label.get(conf, conf)}** — {block["reason"]}')
        if conf != 'high':
            if rk == 'proficiency':
                fix = (
                    'Tăng số lượt nghe/nói/đọc có điểm; bảo đảm log từ vựng & ngữ pháp (attempt) '
                    'và averagePronunciationScore khi có thể.'
                )
            elif rk == 'capacity':
                fix = 'Bật đồng bộ sectionsCompletionPercent và averageReactionTimeMs từ LMS cho mỗi buổi.'
            elif rk == 'engagement':
                fix = 'Ghi nhận speakingTurnCount (và nên có speakingCoverage nếu platform hỗ trợ).'
            else:
                fix = (
                    'Khuyến khích GV nhập teacherComment/sessionSummary ngắn sau buổi; '
                    'kết hợp completion + reaction để suy ra tự điều chỉnh.'
                )
            lines.append(f'  - Cách củng cố: {fix}')
    lines.append('')
    return '\n'.join(lines)


def format_portfolio_appendix_markdown(skill_snapshot_pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    if not skill_snapshot_pairs:
        return ''

    agg_prof: list[str] = []
    agg_cap: list[str] = []
    agg_eng: list[str] = []
    agg_sr: list[str] = []
    listen_counts: list[int] = []
    speak_counts: list[int] = []
    read_counts: list[int] = []

    for skill_ctx, snap in skill_snapshot_pairs:
        dq = build_lesson_rubric_data_quality(skill_ctx, snap)
        rub = dq['rubric_criteria']
        agg_prof.append(rub['proficiency']['system_confidence'])
        agg_cap.append(rub['capacity']['system_confidence'])
        agg_eng.append(rub['engagement']['system_confidence'])
        agg_sr.append(rub['self_regulation']['system_confidence'])
        p = dq['skill_pillars']
        listen_counts.append(int(p['listening']['attempt_count']))
        speak_counts.append(int(p['speaking']['attempt_count']))
        read_counts.append(int(p['reading']['attempt_count']))

    def _worst(levels: list[str]) -> str:
        if any(x == 'low' for x in levels):
            return 'low'
        if any(x == 'medium' for x in levels):
            return 'medium'
        return 'high'

    n_lessons = len(skill_snapshot_pairs)
    worst_prof = _worst(agg_prof)
    worst_cap = _worst(agg_cap)
    worst_eng = _worst(agg_eng)
    worst_sr = _worst(agg_sr)

    label = {'low': 'Thấp', 'medium': 'Trung bình', 'high': 'Cao'}
    lines = [
        '## Phụ lục (hệ thống): Độ tin cậy dữ liệu tổng hợp',
        '',
        f'_Tổng hợp từ **{n_lessons}** buổi trong tập portfolio; lấy mức kém nhất giữa các buổi._',
        '',
        f'- **Proficiency (tổng)**: độ tin cậy hệ thống — **{label[worst_prof]}**.',
        f'- **Capacity (tổng)**: độ tin cậy hệ thống — **{label[worst_cap]}**.',
        f'- **Engagement (tổng)**: độ tin cậy hệ thống — **{label[worst_eng]}**.',
        f'- **Self-regulation (tổng)**: độ tin cậy hệ thống — **{label[worst_sr]}**.',
        '',
        '### Trung bình lượt có điểm / buổi (tham khảo)',
        f'- Nghe: {sum(listen_counts) / n_lessons:.1f}',
        f'- Nói (ước lượng từ log): {sum(speak_counts) / n_lessons:.1f}',
        f'- Đọc: {sum(read_counts) / n_lessons:.1f}',
        '',
        '### Củng cố đánh giá khi tổng hợp còn yếu',
        '- Chuẩn hóa log đủ trường: speakingTurnCount, sectionsCompletionPercent, averageReactionTimeMs cho mọi buổi.',
        '- Mỗi buổi nên có tối thiểu vài lượt nghe + nói + đọc có điểm để rubric 4 tiêu chí không suy diễn từ một nguồn.',
        '- GV ghi teacherComment/sessionSummary ngắn sau buổi để bổ sung tiêu chí quan sát (engagement, self-regulation).',
        '',
    ]
    return '\n'.join(lines)
