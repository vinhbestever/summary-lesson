import json
import os
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


def generate_summary(report_text: str) -> dict:
    return summarize_report(report_text)


def generate_lesson_feedback(report_text: str, lesson_label: str | None = None) -> dict:
    return generate_lesson_feedback_from_llm(report_text, lesson_label)


def stream_lesson_feedback(report_text: str, lesson_label: str | None = None):
    return stream_lesson_feedback_from_llm(report_text, lesson_label)


def generate_portfolio_feedback(lessons_payload: list[dict], portfolio_label: str | None = None) -> dict:
    return generate_portfolio_feedback_from_llm(lessons_payload, portfolio_label)


def stream_portfolio_feedback(lessons_payload: list[dict], portfolio_label: str | None = None):
    return stream_portfolio_feedback_from_llm(lessons_payload, portfolio_label)


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


def _parse_lesson_time_to_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace(' ', 'T')
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def _extract_lesson_snapshot(raw_json_text: str, lesson_id: str, source_file: str) -> dict[str, Any]:
    root = _parse_lesson_root(raw_json_text)
    lesson_time = root.get('lessonTime') if isinstance(root.get('lessonTime'), dict) else {}
    achievements = root.get('achievements') if isinstance(root.get('achievements'), dict) else {}
    stats = achievements.get('stats') if isinstance(achievements.get('stats'), dict) else {}
    pronunciation = (
        achievements.get('pronunciation') if isinstance(achievements.get('pronunciation'), dict) else {}
    )
    vocabulary_attempts = achievements.get('vocabulary') if isinstance(achievements.get('vocabulary'), list) else []
    grammar_attempts = achievements.get('grammar') if isinstance(achievements.get('grammar'), list) else []
    targets = root.get('targets') if isinstance(root.get('targets'), dict) else {}
    target_vocabulary = targets.get('vocabulary') if isinstance(targets.get('vocabulary'), list) else []
    target_grammar = targets.get('grammar') if isinstance(targets.get('grammar'), list) else []
    script_metadata = root.get('scriptMetadata') if isinstance(root.get('scriptMetadata'), dict) else {}

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
        current_lesson_data = parsed_current

    payload = {
        'current_lesson_data': current_lesson_data,
        'lesson_progress_context': _build_lesson_progress_context(current_report_text, lesson_id),
    }
    return json.dumps(payload, ensure_ascii=False)


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
                    yield _format_sse_event(event_type, json.dumps(event.get('data', {}), ensure_ascii=False))
                else:
                    yield _format_sse_event(event_type, json.dumps(event, ensure_ascii=False))
        except Exception as exc:
            stream_failed = True
            yield _format_sse_event('error', str(exc))
        if not stream_failed:
            write_feedback_cache(cache_key, ''.join(chunk_buffer))
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
        if not lessons_payload:
            raise HTTPException(status_code=400, detail='Khong tim thay du lieu lesson trong /data')
        feedback = generate_portfolio_feedback(lessons_payload, payload.portfolio_label)
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
            yield _format_sse_event('done', 'done')

        return StreamingResponse(
            cached_event_generator(),
            media_type='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'},
        )

    try:
        lessons_payload = load_all_lessons_json_from_local_data()
        if not lessons_payload:
            raise HTTPException(status_code=400, detail='Khong tim thay du lieu lesson trong /data')
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Unexpected portfolio feedback error') from exc

    def event_generator():
        chunk_buffer: list[str] = []
        stream_failed = False
        try:
            for event in stream_portfolio_feedback(lessons_payload, payload.portfolio_label):
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
                    yield _format_sse_event(event_type, json.dumps(event.get('data', {}), ensure_ascii=False))
                else:
                    yield _format_sse_event(event_type, json.dumps(event, ensure_ascii=False))
        except Exception as exc:
            stream_failed = True
            yield _format_sse_event('error', str(exc))
        if not stream_failed:
            write_feedback_cache(cache_key, ''.join(chunk_buffer))
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
