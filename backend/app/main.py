import json
import os
import re
import unicodedata
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from app.feedback_cache import (
    lesson_feedback_cache_key,
    portfolio_feedback_cache_key,
    read_feedback_cache,
    write_feedback_cache,
)
from app.ingest import (
    build_report_url_from_lesson_id,
    fetch_report_text_from_url,
    load_all_lessons_json_from_local_data,
    load_lesson_json_from_local_data,
)
from app.rubric_quality import (
    build_lesson_rubric_data_quality,
    format_lesson_appendix_markdown,
    format_portfolio_appendix_markdown,
)
from app.llm import generate_lesson_feedback as generate_lesson_feedback_from_llm
from app.llm import generate_portfolio_feedback as generate_portfolio_feedback_from_llm
from app.llm import stream_lesson_feedback as stream_lesson_feedback_from_llm
from app.llm import stream_portfolio_feedback as stream_portfolio_feedback_from_llm
from app.llm import summarize_report
from app.schemas import (
    LessonFeedbackRequest,
    PortfolioFeedbackRequest,
    ReportInputRequest,
    SummaryRequest,
    SummaryResponse,
)

load_dotenv()

app = FastAPI(title='Summary Lesson API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

_RADAR_COMPETENCY_SPECS = [
    ('proficiency', 'A', 'Proficiency'),
    ('capacity', 'B', 'Capacity'),
    ('engagement', 'C', 'Engagement'),
    ('self_regulation', 'D', 'Self-regulation'),
]
_RADAR_COMPETENCY_BY_NAME = {
    'proficiency': 'proficiency',
    'capacity': 'capacity',
    'engagement': 'engagement',
    'self-regulation': 'self_regulation',
    'self regulation': 'self_regulation',
    'selfregulation': 'self_regulation',
}
_RADAR_COMPETENCY_BY_CODE = {code.upper(): key for key, code, _name in _RADAR_COMPETENCY_SPECS}
# In-class rubric (3 levels) + legacy 5-level labels for older markdown
_LEVEL_SCORE_MAP = {
    'Exceeds Expectation': 90,
    'Vượt kỳ vọng': 90,
    'Meets Expectation': 60,
    'Đạt kỳ vọng': 60,
    'Needs Improvement': 25,
    'Cần cải thiện': 25,
    'Rất cần hỗ trợ': 20,
    'Cần hỗ trợ': 40,
    'Đang hình thành': 60,
    'Khá vững': 80,
    'Vững vàng': 100,
}
_LEVEL_LABELS_BY_LENGTH = sorted(_LEVEL_SCORE_MAP.keys(), key=len, reverse=True)


def generate_summary(report_text: str) -> dict:
    return summarize_report(report_text)


def generate_lesson_feedback(report_text: str, lesson_label: str | None = None) -> dict:
    return generate_lesson_feedback_from_llm(report_text, lesson_label)


def stream_lesson_feedback(report_text: str, lesson_label: str | None = None):
    return stream_lesson_feedback_from_llm(report_text, lesson_label)


def generate_portfolio_feedback(
    lessons_payload: list[dict],
    portfolio_label: str | None = None,
    portfolio_rubric_per_lesson: list[dict[str, Any]] | None = None,
) -> dict:
    return generate_portfolio_feedback_from_llm(
        lessons_payload, portfolio_label, portfolio_rubric_per_lesson=portfolio_rubric_per_lesson
    )


def stream_portfolio_feedback(
    lessons_payload: list[dict],
    portfolio_label: str | None = None,
    portfolio_rubric_per_lesson: list[dict[str, Any]] | None = None,
):
    return stream_portfolio_feedback_from_llm(
        lessons_payload, portfolio_label, portfolio_rubric_per_lesson=portfolio_rubric_per_lesson
    )


def resolve_report_text(payload: ReportInputRequest) -> str:
    if payload.report_text:
        return payload.report_text

    if payload.report_url:
        return fetch_report_text_from_url(payload.report_url)

    if payload.lesson_id:
        local_lesson_json = load_lesson_json_from_local_data(payload.lesson_id)
        if local_lesson_json:
            return local_lesson_json
        report_url = build_report_url_from_lesson_id(payload.lesson_id)
        return fetch_report_text_from_url(report_url)

    raise ValueError('No report input was provided')


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


def _extract_lesson_moments(root: dict[str, Any], primary_report: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(root.get('moments'), list):
        return [item for item in root.get('moments', []) if isinstance(item, dict)]
    if isinstance(primary_report.get('moments'), list):
        return [item for item in primary_report.get('moments', []) if isinstance(item, dict)]
    return []


def _words_count(value: Any) -> int:
    text = str(value or '').strip()
    if not text:
        return 0
    return len([part for part in text.split() if part.strip()])


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _take_examples(values: list[str], limit: int = 3) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= limit:
            break
    return deduped


def _normalize_compare_text(value: str) -> str:
    normalized = unicodedata.normalize('NFD', value or '')
    without_marks = ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')
    return without_marks.lower().strip()


def _extract_level_label(value: str) -> str:
    normalized_value = _normalize_compare_text(value)
    for label in _LEVEL_LABELS_BY_LENGTH:
        if _normalize_compare_text(label) in normalized_value:
            return label
    return ''


def _extract_competency_score(line: str) -> tuple[int | None, str, bool]:
    content = line.split(':', 1)[1].strip() if ':' in line else ''
    normalized_content = _normalize_compare_text(content)
    insufficient_data = 'chua du du lieu' in normalized_content

    level_text = _extract_level_label(content)
    score: int | None = None
    score_match = re.search(r'(?<!\d)(100|[1-9]?\d)(?:\s*/\s*100)?', content)
    if score_match:
        score = max(0, min(int(score_match.group(1)), 100))
    elif level_text:
        score = _LEVEL_SCORE_MAP[level_text]

    if insufficient_data:
        return 0, level_text, True
    return score, level_text, False


def _default_lesson_radar_payload() -> dict[str, Any]:
    return {
        'type': 'lesson_radar',
        'competencies': [
            {
                'key': key,
                'label': f'{code}. {name}',
                'score': 0,
                'level_text': '',
                'insufficient_data': True,
            }
            for key, code, name in _RADAR_COMPETENCY_SPECS
        ],
    }


def _build_lesson_radar_payload(markdown: str) -> dict[str, Any]:
    payload = _default_lesson_radar_payload()
    lines = (markdown or '').splitlines()
    if not lines:
        return payload

    inside_section = False
    current_key: str | None = None
    competency_data: dict[str, dict[str, Any]] = {}

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped:
            continue

        if re.match(r'^##\s+', stripped):
            if re.match(
                r'^##\s*(Đánh giá 4 tiêu chí|Danh gia 4 tieu chi|Đánh giá 6 năng lực|Danh gia 6 nang luc)\b',
                stripped,
                flags=re.IGNORECASE,
            ):
                inside_section = True
                current_key = None
                continue
            if inside_section:
                break
            continue

        if not inside_section:
            continue

        competency_match = re.match(
            r'^[-*]\s*(?:([A-D])\.\s*)?(?:\*\*)?'
            r'(Proficiency|Capacity|Engagement|Self-regulation|Self regulation)'
            r'(?:\*\*)?\b',
            stripped,
            flags=re.IGNORECASE,
        )
        legacy_match = re.match(
            r'^[-*]\s*(?:([A-F])\.\s*)?(?:\*\*)?(Learn|Recognize|Apply|Retain|Focus|Express)(?:\*\*)?\b',
            stripped,
            flags=re.IGNORECASE,
        )
        if competency_match:
            code = (competency_match.group(1) or '').upper()
            name = re.sub(r'\s+', ' ', competency_match.group(2).strip().lower())
            name_key = name.replace(' ', '-')
            current_key = _RADAR_COMPETENCY_BY_NAME.get(name_key) or _RADAR_COMPETENCY_BY_CODE.get(code)
            if current_key and current_key not in competency_data:
                competency_data[current_key] = {'score': None, 'level_text': '', 'insufficient_data': True}
            continue
        if legacy_match:
            _legacy_map = {
                'learn': 'proficiency',
                'recognize': 'proficiency',
                'apply': 'proficiency',
                'retain': 'capacity',
                'focus': 'self_regulation',
                'express': 'engagement',
            }
            code = (legacy_match.group(1) or '').upper()
            name = legacy_match.group(2).lower()
            current_key = _legacy_map.get(name) or _RADAR_COMPETENCY_BY_CODE.get(code)
            if current_key and current_key not in competency_data:
                competency_data[current_key] = {'score': None, 'level_text': '', 'insufficient_data': True}
            continue

        if current_key is None:
            continue

        if 'ket qua hien tai' in _normalize_compare_text(stripped):
            score, level_text, insufficient_data = _extract_competency_score(stripped)
            competency_data[current_key] = {
                'score': score,
                'level_text': level_text,
                'insufficient_data': insufficient_data or score is None,
            }

    normalized_competencies: list[dict[str, Any]] = []
    for key, code, name in _RADAR_COMPETENCY_SPECS:
        item = competency_data.get(key, {})
        score = item.get('score')
        insufficient = bool(item.get('insufficient_data', True))
        normalized_competencies.append(
            {
                'key': key,
                'label': f'{code}. {name}',
                'score': int(score) if isinstance(score, int) else 0,
                'level_text': str(item.get('level_text') or ''),
                'insufficient_data': insufficient or score is None,
            }
        )

    payload['competencies'] = normalized_competencies
    return payload


def _build_lesson_skill_context(raw_json_text: str) -> dict[str, Any]:
    root = _parse_lesson_root(raw_json_text)
    primary_report = _extract_primary_report(root)
    moments = _extract_lesson_moments(root, primary_report)

    vocab_scores: list[float] = []
    vocab_evidence: list[str] = []
    short_sentence_scores: list[float] = []
    short_sentence_evidence: list[str] = []
    long_sentence_scores: list[float] = []
    long_sentence_evidence: list[str] = []
    listening_scores: list[float] = []
    listening_questions: list[str] = []
    listening_good_examples: list[str] = []
    listening_weak_examples: list[str] = []
    reading_scores: list[float] = []
    reading_good_examples: list[str] = []
    reading_weak_examples: list[str] = []

    for moment in moments:
        interaction_type = str(moment.get('interaction_type') or moment.get('interactionType') or '').strip()
        lms_type = str(moment.get('lms_type') or moment.get('lmsType') or '').strip()
        lms_data = moment.get('lms_data') if isinstance(moment.get('lms_data'), dict) else {}
        if not lms_data and isinstance(moment.get('lmsData'), dict):
            lms_data = moment.get('lmsData')
        result = moment.get('result') if isinstance(moment.get('result'), dict) else {}
        question_type = str(lms_data.get('questionType') or '').strip()
        expected_transcript = str(lms_data.get('expectedTranscript') or '').strip()
        user_transcript = str(result.get('userTranscript') or '').strip()
        score = _to_float(result.get('score'))
        pronunciation_score = _to_float(result.get('pronunciationScore'))
        activity_score = pronunciation_score if pronunciation_score is not None else score
        transcript_for_example = user_transcript or expected_transcript

        is_audio = interaction_type == 'AUDIO'
        if is_audio and expected_transcript:
            expected_word_count = _words_count(expected_transcript)
            if expected_word_count <= 3:
                if activity_score is not None:
                    vocab_scores.append(activity_score)
                if transcript_for_example:
                    vocab_evidence.append(transcript_for_example)

            is_short_activity = lms_type == 'game_pronunciation' or (
                question_type == 'speaking_scripted' and expected_word_count <= 4
            )
            is_long_activity = lms_type in {'dialogue', 'conversation'} or (
                question_type == 'speaking_scripted' and expected_word_count >= 5
            )

            if is_short_activity:
                if score is not None:
                    short_sentence_scores.append(score)
                if transcript_for_example:
                    short_sentence_evidence.append(transcript_for_example)

            if is_long_activity:
                if score is not None:
                    long_sentence_scores.append(score)
                if transcript_for_example:
                    long_sentence_evidence.append(transcript_for_example)

            # Read-aloud evidence: scripted speaking or dialogue/conversation with expected transcript.
            is_reading_activity = lms_type in {'dialogue', 'conversation', 'game_pronunciation'} or (
                question_type == 'speaking_scripted'
            )
            if is_reading_activity and score is not None:
                reading_scores.append(score)
                pair = f'expected="{expected_transcript}" | spoken="{user_transcript or "không có bản ghi"}"'
                if score >= 85:
                    reading_good_examples.append(pair)
                elif score <= 70:
                    reading_weak_examples.append(pair)

        is_listening_quiz = question_type in {'single_choice', 'matching'}
        if is_listening_quiz:
            if score is not None:
                listening_scores.append(score)
            question = str(lms_data.get('question') or '').strip()
            if question:
                listening_questions.append(question)
                if score is not None:
                    item = f'question="{question}" | score={round(score, 2)}'
                    if score >= 80:
                        listening_good_examples.append(item)
                    elif score < 80:
                        listening_weak_examples.append(item)

    speaking_sentence_total = len(short_sentence_scores) + len(long_sentence_scores)
    listening_correct_count = len([value for value in listening_scores if value >= 80])
    listening_total = len(listening_scores)

    return {
        'speaking_pronunciation_vocab': {
            'attempt_count': len(vocab_scores),
            'average_score': _avg(vocab_scores),
            'evidence': _take_examples(vocab_evidence),
        },
        'speaking_sentence_length_by_activity': {
            'short_sentence': {
                'attempt_count': len(short_sentence_scores),
                'average_score': _avg(short_sentence_scores),
                'evidence': _take_examples(short_sentence_evidence),
            },
            'long_sentence': {
                'attempt_count': len(long_sentence_scores),
                'average_score': _avg(long_sentence_scores),
                'evidence': _take_examples(long_sentence_evidence),
            },
            'total_attempt_count': speaking_sentence_total,
        },
        'listening_quiz': {
            'attempt_count': listening_total,
            'correct_count': listening_correct_count,
            'accuracy_percent': round((listening_correct_count / listening_total) * 100, 2)
            if listening_total
            else None,
            'evidence_questions': _take_examples(listening_questions),
            'good_examples': _take_examples(listening_good_examples),
            'weak_examples': _take_examples(listening_weak_examples),
        },
        'reading_fluency': {
            'attempt_count': len(reading_scores),
            'average_score': _avg(reading_scores),
            'good_examples': _take_examples(reading_good_examples),
            'weak_examples': _take_examples(reading_weak_examples),
        },
        'data_coverage': {
            'speaking_pronunciation_vocab': len(vocab_scores) > 0,
            'speaking_sentence_length': speaking_sentence_total > 0,
            'listening_quiz': listening_total > 0,
            'reading_fluency': len(reading_scores) > 0,
        },
    }


def _parse_lesson_time_to_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace(' ', 'T')
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def _is_trial_lesson(lesson_id: str) -> bool:
    return lesson_id.upper().startswith('TRIAL_')


def _lesson_id_desc_sort_key(lesson_id: str) -> tuple[int, int, str]:
    lesson_id = lesson_id.strip()
    if lesson_id.isdigit():
        return (1, int(lesson_id), lesson_id)
    return (0, 0, lesson_id.lower())


def _extract_lesson_start_time_from_raw_json(raw_json_text: str) -> str | None:
    root = _parse_lesson_root(raw_json_text)
    report = _extract_primary_report(root)
    lesson_time = report.get('lessonTime') if isinstance(report.get('lessonTime'), dict) else {}
    start_time = lesson_time.get('lessonStartTime') if isinstance(lesson_time, dict) else None
    if isinstance(start_time, str):
        return start_time
    return None


def _select_recent_portfolio_lessons(
    lessons_payload: list[dict[str, str]],
    limit: int = 8,
) -> list[dict[str, str]]:
    candidates: list[dict[str, Any]] = []

    for item in lessons_payload:
        lesson_id = str(item.get('lesson_id', '')).strip()
        if not lesson_id or _is_trial_lesson(lesson_id):
            continue
        start_time = _extract_lesson_start_time_from_raw_json(item.get('raw_json_text', ''))
        time_sort_key = _parse_lesson_time_to_timestamp(start_time)
        candidates.append(
            {
                'item': item,
                'lesson_id': lesson_id,
                'time_sort_key': time_sort_key,
            }
        )

    candidates.sort(
        key=lambda entry: (
            entry.get('time_sort_key') is not None,
            entry.get('time_sort_key') or float('-inf'),
            _lesson_id_desc_sort_key(str(entry.get('lesson_id', ''))),
        ),
        reverse=True,
    )
    return [entry['item'] for entry in candidates[: max(0, limit)]]


def _extract_lesson_snapshot(raw_json_text: str, lesson_id: str, source_file: str) -> dict[str, Any]:
    root = _parse_lesson_root(raw_json_text)
    report = _extract_primary_report(root)
    lesson_time = report.get('lessonTime') if isinstance(report.get('lessonTime'), dict) else {}
    achievements = report.get('achievements') if isinstance(report.get('achievements'), dict) else {}
    stats = achievements.get('stats') if isinstance(achievements.get('stats'), dict) else {}
    pronunciation = (
        achievements.get('pronunciation') if isinstance(achievements.get('pronunciation'), dict) else {}
    )
    vocabulary_attempts = achievements.get('vocabulary') if isinstance(achievements.get('vocabulary'), list) else []
    grammar_attempts = achievements.get('grammar') if isinstance(achievements.get('grammar'), list) else []
    targets = report.get('targets') if isinstance(report.get('targets'), dict) else {}
    target_vocabulary = targets.get('vocabulary') if isinstance(targets.get('vocabulary'), list) else []
    target_grammar = targets.get('grammar') if isinstance(targets.get('grammar'), list) else []
    script_metadata = report.get('scriptMetadata') if isinstance(report.get('scriptMetadata'), dict) else {}

    start_time = lesson_time.get('lessonStartTime') if isinstance(lesson_time, dict) else None
    end_time = lesson_time.get('lessonEndTime') if isinstance(lesson_time, dict) else None

    weak_vocabulary = sorted(
        [
            {
                'word': str(item.get('word', '')).strip(),
                'average_score': item.get('averageScore'),
            }
            for item in vocabulary_attempts
            if isinstance(item, dict) and str(item.get('word', '')).strip()
        ],
        key=lambda item: float(item.get('average_score') or 0),
    )[:3]

    return {
        'lesson_id': lesson_id,
        'source_file': source_file,
        'script_name': script_metadata.get('name'),
        'lesson_time': {
            'lesson_start_time': start_time,
            'lesson_end_time': end_time,
        },
        'targets': {
            'vocabulary': [str(item).strip() for item in target_vocabulary if str(item).strip()],
            'grammar': [str(item).strip() for item in target_grammar if str(item).strip()],
        },
        'stats': {
            'speaking_turn_count': stats.get('speakingTurnCount'),
            'average_reaction_time_ms': stats.get('averageReactionTimeMs'),
            'sections_completion_percent': stats.get('sectionsCompletionPercent'),
            'average_pronunciation_score': pronunciation.get('averagePronunciationScore'),
            'teacher_comment': stats.get('teacherComment'),
            'session_summary': stats.get('sessionSummary'),
        },
        'skill_evidence': {
            'weak_vocabulary': weak_vocabulary,
            'vocabulary_attempt_count': len(vocabulary_attempts),
            'grammar_attempt_count': len(grammar_attempts),
        },
        'time_sort_key': _parse_lesson_time_to_timestamp(start_time),
    }


def _build_lesson_progress_context(current_report_text: str, lesson_id: str | None) -> dict[str, Any]:
    current_id = (lesson_id or '').strip()
    if not current_id:
        return {
            'current_lesson': _extract_lesson_snapshot(current_report_text, 'unknown', 'request_input'),
            'recent_lessons': [],
            'progress_context': {
                'is_first_lesson': True,
                'reason': 'current_lesson_not_identified',
                'comparison_basis': 'lessonTime.lessonStartTime',
            },
        }

    current_snapshot = _extract_lesson_snapshot(current_report_text, current_id, f'lesson_{current_id}.json')
    current_time_sort_key = current_snapshot.get('time_sort_key')
    if current_time_sort_key is None:
        return {
            'current_lesson': current_snapshot,
            'recent_lessons': [],
            'progress_context': {
                'is_first_lesson': True,
                'reason': 'missing_current_lesson_time',
                'comparison_basis': 'lessonTime.lessonStartTime',
            },
        }

    lesson_items = load_all_lessons_json_from_local_data()
    previous_lessons: list[dict[str, Any]] = []
    for item in lesson_items:
        candidate_id = str(item.get('lesson_id', '')).strip()
        if not candidate_id or candidate_id == current_id:
            continue
        snapshot = _extract_lesson_snapshot(
            item.get('raw_json_text', ''),
            candidate_id,
            str(item.get('source_file', '')),
        )
        candidate_time_sort_key = snapshot.get('time_sort_key')
        if candidate_time_sort_key is None:
            continue
        if candidate_time_sort_key < current_time_sort_key:
            previous_lessons.append(snapshot)

    previous_lessons.sort(key=lambda item: item.get('time_sort_key') or 0, reverse=True)
    recent_lessons = previous_lessons[:2]

    return {
        'current_lesson': current_snapshot,
        'recent_lessons': recent_lessons,
        'progress_context': {
            'is_first_lesson': len(recent_lessons) == 0,
            'reason': 'no_previous_lessons' if len(recent_lessons) == 0 else 'has_recent_lessons',
            'comparison_basis': 'lessonTime.lessonStartTime',
        },
    }


def _build_lesson_feedback_input_text(current_report_text: str, lesson_id: str | None) -> str:
    current_lesson_data: Any = current_report_text
    parsed_current = _parse_lesson_root(current_report_text)
    if parsed_current:
        primary_report = _extract_primary_report(parsed_current)
        current_lesson_data = primary_report or parsed_current

    lesson_skill_context = _build_lesson_skill_context(current_report_text)
    lesson_progress_context = _build_lesson_progress_context(current_report_text, lesson_id)
    current_snapshot = lesson_progress_context.get('current_lesson')
    current_snapshot = current_snapshot if isinstance(current_snapshot, dict) else {}

    payload = {
        'current_lesson_data': current_lesson_data,
        'lesson_progress_context': lesson_progress_context,
        'lesson_skill_context': lesson_skill_context,
        'rubric_data_quality': build_lesson_rubric_data_quality(lesson_skill_context, current_snapshot),
    }
    return json.dumps(payload, ensure_ascii=False)


def _lesson_appendix_only(report_text: str, lesson_id: str | None) -> str:
    skill_ctx = _build_lesson_skill_context(report_text)
    progress = _build_lesson_progress_context(report_text, lesson_id)
    snap = progress.get('current_lesson')
    snap = snap if isinstance(snap, dict) else {}
    return format_lesson_appendix_markdown(skill_ctx, snap).strip()


def _append_lesson_system_appendix(markdown: str, report_text: str, lesson_id: str | None) -> str:
    appendix = _lesson_appendix_only(report_text, lesson_id)
    base = (markdown or '').strip()
    if appendix and 'Phụ lục (hệ thống)' in base:
        return base
    if not base:
        return appendix
    if not appendix:
        return base
    return f'{base.rstrip()}\n\n{appendix}'.strip()


def _portfolio_rubric_per_lesson_and_pairs(
    selected_lessons: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[tuple[dict[str, Any], dict[str, Any]]]]:
    per_lesson: list[dict[str, Any]] = []
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in selected_lessons:
        raw = str(item.get('raw_json_text', ''))
        lid = str(item.get('lesson_id', '')).strip() or 'unknown'
        src = str(item.get('source_file', ''))
        skill_ctx = _build_lesson_skill_context(raw)
        snapshot = _extract_lesson_snapshot(raw, lid, src)
        dq = build_lesson_rubric_data_quality(skill_ctx, snapshot)
        per_lesson.append({'lesson_id': lid, 'source_file': src, 'rubric_data_quality': dq})
        pairs.append((skill_ctx, snapshot))
    return per_lesson, pairs


def _portfolio_appendix_only(selected_lessons: list[dict[str, str]]) -> str:
    _per, pairs = _portfolio_rubric_per_lesson_and_pairs(selected_lessons)
    return format_portfolio_appendix_markdown(pairs).strip()


def _append_portfolio_system_appendix(markdown: str, selected_lessons: list[dict[str, str]]) -> str:
    appendix = _portfolio_appendix_only(selected_lessons)
    base = (markdown or '').strip()
    if appendix and 'Phụ lục (hệ thống)' in base:
        return base
    if not appendix:
        return base
    if not base:
        return appendix
    return f'{base.rstrip()}\n\n{appendix}'.strip()


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/api/v1/summaries', response_model=SummaryResponse)
def create_summary(payload: SummaryRequest) -> SummaryResponse:
    try:
        report_text = resolve_report_text(payload)
        summary = generate_summary(report_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to load report: {exc}') from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f'Invalid summarization input/output: {exc}') from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Unexpected summarization error') from exc

    return SummaryResponse(**summary)


@app.post('/api/v1/lesson-feedback', response_class=PlainTextResponse)
def create_lesson_feedback(payload: LessonFeedbackRequest) -> PlainTextResponse:
    cache_key = lesson_feedback_cache_key(payload.lesson_id, payload.report_text, payload.report_url, payload.lesson_label)
    cached_markdown = read_feedback_cache(cache_key)
    if cached_markdown is not None:
        return PlainTextResponse(content=cached_markdown, media_type='text/markdown')

    try:
        report_text = resolve_report_text(payload)
        lesson_feedback_input_text = _build_lesson_feedback_input_text(report_text, payload.lesson_id)
        feedback = generate_lesson_feedback(lesson_feedback_input_text, payload.lesson_label)
        feedback = _append_lesson_system_appendix(feedback, report_text, payload.lesson_id)
        write_feedback_cache(cache_key, feedback)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to load report: {exc}') from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f'Invalid lesson feedback input/output: {exc}') from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Unexpected lesson feedback error') from exc

    return PlainTextResponse(content=feedback, media_type='text/markdown')


def _format_sse_event(event_name: str, data: str) -> str:
    data_lines = (data or '').splitlines() or ['']
    formatted_data = '\n'.join(f'data: {line}' for line in data_lines)
    return f'event: {event_name}\n{formatted_data}\n\n'


@app.post('/api/v1/lesson-feedback/stream')
def create_lesson_feedback_stream(payload: LessonFeedbackRequest) -> StreamingResponse:
    cache_key = lesson_feedback_cache_key(payload.lesson_id, payload.report_text, payload.report_url, payload.lesson_label)
    cached_markdown = read_feedback_cache(cache_key)
    if cached_markdown is not None:
        def cached_event_generator():
            yield _format_sse_event('status', 'Dang tai noi dung nhan xet tu cache...')
            yield _format_sse_event('chunk', cached_markdown)
            radar_payload = _build_lesson_radar_payload(cached_markdown)
            yield _format_sse_event('result', json.dumps(radar_payload, ensure_ascii=False))
            yield _format_sse_event('done', 'done')

        return StreamingResponse(
            cached_event_generator(),
            media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'},
        )

    try:
        report_text = resolve_report_text(payload)
        lesson_feedback_input_text = _build_lesson_feedback_input_text(report_text, payload.lesson_id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to load report: {exc}') from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f'Invalid lesson feedback input/output: {exc}') from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Unexpected lesson feedback error') from exc

    def event_generator():
        chunk_buffer: list[str] = []
        stream_failed = False
        has_radar_result = False
        try:
            for event in stream_lesson_feedback(lesson_feedback_input_text, payload.lesson_label):
                event_type = str(event.get('type', 'status'))
                if event_type == 'status':
                    yield _format_sse_event(event_type, str(event.get('message', '')))
                elif event_type == 'chunk':
                    chunk_content = str(event.get('content', ''))
                    if chunk_content:
                        chunk_buffer.append(chunk_content)
                    yield _format_sse_event(event_type, chunk_content)
                elif event_type == 'error':
                    stream_failed = True
                    yield _format_sse_event(event_type, str(event.get('message', '')))
                elif event_type == 'result':
                    result_data = event.get('data', {})
                    if isinstance(result_data, dict) and result_data.get('type') == 'lesson_radar':
                        has_radar_result = True
                    yield _format_sse_event(event_type, json.dumps(result_data, ensure_ascii=False))
                else:
                    yield _format_sse_event(event_type, json.dumps(event, ensure_ascii=False))
        except Exception as exc:
            stream_failed = True
            yield _format_sse_event('error', str(exc))
        if not stream_failed:
            raw_markdown = ''.join(chunk_buffer)
            appendix_block = _lesson_appendix_only(report_text, payload.lesson_id)
            base_stripped = (raw_markdown or '').strip()
            if appendix_block and 'Phụ lục (hệ thống)' not in raw_markdown:
                stream_suffix = ('\n\n' + appendix_block) if base_stripped else appendix_block
                yield _format_sse_event('chunk', stream_suffix)
            full_markdown = _append_lesson_system_appendix(raw_markdown, report_text, payload.lesson_id)
            write_feedback_cache(cache_key, full_markdown)
            if not has_radar_result:
                radar_payload = _build_lesson_radar_payload(full_markdown)
                yield _format_sse_event('result', json.dumps(radar_payload, ensure_ascii=False))
        yield _format_sse_event('done', 'done')

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'},
    )


@app.post('/api/v1/portfolio-feedback', response_class=PlainTextResponse)
def create_portfolio_feedback(payload: PortfolioFeedbackRequest) -> PlainTextResponse:
    cache_key = portfolio_feedback_cache_key()
    cached_markdown = read_feedback_cache(cache_key)
    if cached_markdown is not None:
        return PlainTextResponse(content=cached_markdown, media_type='text/markdown')

    try:
        lessons_payload = load_all_lessons_json_from_local_data()
        selected_lessons = _select_recent_portfolio_lessons(lessons_payload, limit=8)
        if not selected_lessons:
            raise HTTPException(status_code=400, detail='Khong tim thay du lieu lesson trong /data')
        rubric_per_lesson, _pairs = _portfolio_rubric_per_lesson_and_pairs(selected_lessons)
        feedback = generate_portfolio_feedback(
            selected_lessons, payload.portfolio_label, portfolio_rubric_per_lesson=rubric_per_lesson
        )
        feedback = _append_portfolio_system_appendix(feedback, selected_lessons)
        write_feedback_cache(cache_key, feedback)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f'Invalid portfolio feedback input/output: {exc}') from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Unexpected portfolio feedback error') from exc

    return PlainTextResponse(content=feedback, media_type='text/markdown')


@app.post('/api/v1/portfolio-feedback/stream')
def create_portfolio_feedback_stream(payload: PortfolioFeedbackRequest) -> StreamingResponse:
    cache_key = portfolio_feedback_cache_key()
    cached_markdown = read_feedback_cache(cache_key)
    if cached_markdown is not None:
        def cached_event_generator():
            yield _format_sse_event('status', 'Dang tai noi dung nhan xet tu cache...')
            yield _format_sse_event('chunk', cached_markdown)
            radar_payload = _build_lesson_radar_payload(cached_markdown)
            yield _format_sse_event('result', json.dumps(radar_payload, ensure_ascii=False))
            yield _format_sse_event('done', 'done')

        return StreamingResponse(
            cached_event_generator(),
            media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'},
        )

    try:
        lessons_payload = load_all_lessons_json_from_local_data()
        selected_lessons = _select_recent_portfolio_lessons(lessons_payload, limit=8)
        if not selected_lessons:
            raise HTTPException(status_code=400, detail='Khong tim thay du lieu lesson trong /data')
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Unexpected portfolio feedback error') from exc

    rubric_per_lesson, _ = _portfolio_rubric_per_lesson_and_pairs(selected_lessons)

    def event_generator():
        chunk_buffer: list[str] = []
        stream_failed = False
        has_radar_result = False
        try:
            for event in stream_portfolio_feedback(
                selected_lessons,
                payload.portfolio_label,
                portfolio_rubric_per_lesson=rubric_per_lesson,
            ):
                event_type = str(event.get('type', 'status'))
                if event_type == 'status':
                    yield _format_sse_event(event_type, str(event.get('message', '')))
                elif event_type == 'chunk':
                    chunk_content = str(event.get('content', ''))
                    if chunk_content:
                        chunk_buffer.append(chunk_content)
                    yield _format_sse_event(event_type, chunk_content)
                elif event_type == 'error':
                    stream_failed = True
                    yield _format_sse_event(event_type, str(event.get('message', '')))
                elif event_type == 'result':
                    result_data = event.get('data', {})
                    if isinstance(result_data, dict) and result_data.get('type') == 'lesson_radar':
                        has_radar_result = True
                    yield _format_sse_event(event_type, json.dumps(result_data, ensure_ascii=False))
                else:
                    yield _format_sse_event(event_type, json.dumps(event, ensure_ascii=False))
        except Exception as exc:
            stream_failed = True
            yield _format_sse_event('error', str(exc))
        if not stream_failed:
            raw_markdown = ''.join(chunk_buffer)
            appendix_block = _portfolio_appendix_only(selected_lessons)
            base_stripped = (raw_markdown or '').strip()
            if appendix_block and 'Phụ lục (hệ thống)' not in raw_markdown:
                stream_suffix = ('\n\n' + appendix_block) if base_stripped else appendix_block
                yield _format_sse_event('chunk', stream_suffix)
            full_markdown = _append_portfolio_system_appendix(raw_markdown, selected_lessons)
            write_feedback_cache(cache_key, full_markdown)
            if not has_radar_result:
                radar_payload = _build_lesson_radar_payload(full_markdown)
                yield _format_sse_event('result', json.dumps(radar_payload, ensure_ascii=False))
        yield _format_sse_event('done', 'done')

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'},
    )


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=int(os.getenv('BACKEND_PORT', '8000')),
        reload=True,
    )
