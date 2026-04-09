import json

from app.main import _append_lesson_system_appendix, _build_lesson_feedback_input_text
from app.rubric_quality import build_lesson_rubric_data_quality, format_lesson_appendix_markdown


def test_build_lesson_rubric_data_quality_flags_low_when_empty() -> None:
    skill_ctx = {
        'listening_quiz': {'attempt_count': 0},
        'speaking_pronunciation_vocab': {'attempt_count': 0},
        'speaking_sentence_length_by_activity': {'total_attempt_count': 0},
        'reading_fluency': {'attempt_count': 0},
    }
    snapshot = {'stats': {}, 'skill_evidence': {}}
    dq = build_lesson_rubric_data_quality(skill_ctx, snapshot)
    assert dq['skill_pillars']['listening']['system_confidence'] == 'low'
    assert dq['rubric_criteria']['proficiency']['system_confidence'] == 'low'
    assert dq['rubric_criteria']['capacity']['system_confidence'] == 'low'


def test_format_lesson_appendix_contains_headings() -> None:
    skill_ctx = {
        'listening_quiz': {'attempt_count': 0},
        'speaking_pronunciation_vocab': {'attempt_count': 0},
        'speaking_sentence_length_by_activity': {'total_attempt_count': 0},
        'reading_fluency': {'attempt_count': 0},
    }
    snapshot = {'stats': {'speakingTurnCount': 10, 'sectionsCompletionPercent': 80, 'averageReactionTimeMs': 1500}}
    md = format_lesson_appendix_markdown(skill_ctx, snapshot)
    assert 'Phụ lục (hệ thống)' in md
    assert 'Proficiency' in md
    assert 'Cách củng cố' in md


def test_lesson_feedback_input_includes_rubric_data_quality() -> None:
    raw = json.dumps(
        {
            'achievements': {
                'stats': {'speakingTurnCount': 5},
            }
        }
    )
    payload = json.loads(_build_lesson_feedback_input_text(raw, '99'))
    assert payload['rubric_data_quality']['rubric_criteria']['engagement']['system_confidence'] in (
        'low',
        'medium',
        'high',
    )


def test_append_lesson_system_appendix_appends_after_llm_body() -> None:
    report = json.dumps({'achievements': {'stats': {'speakingTurnCount': 2}}})
    out = _append_lesson_system_appendix('# Nhan xet\n\n## Tong quan\n\nOK', report, '1')
    assert out.startswith('# Nhan xet')
    assert 'Phụ lục (hệ thống)' in out
