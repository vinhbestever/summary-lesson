import os
import json

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

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
    allow_origins=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ],
    allow_credentials=True,
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
    try:
        report_text = resolve_report_text(payload)
        feedback = generate_lesson_feedback(report_text, payload.lesson_label)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to load report: {exc}') from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f'Invalid lesson feedback input/output: {exc}') from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Unexpected lesson feedback error') from exc

    return PlainTextResponse(content=feedback, media_type='text/markdown')


def _format_sse_event(event_name: str, data: dict) -> str:
    return f'event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'


@app.post('/api/v1/lesson-feedback/stream')
def create_lesson_feedback_stream(payload: LessonFeedbackRequest) -> StreamingResponse:
    try:
        report_text = resolve_report_text(payload)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to load report: {exc}') from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=f'Invalid lesson feedback input/output: {exc}') from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Unexpected lesson feedback error') from exc

    def event_generator():
        try:
            for event in stream_lesson_feedback(report_text, payload.lesson_label):
                event_type = str(event.get('type', 'status'))
                yield _format_sse_event(event_type, event)
        except Exception as exc:
            yield _format_sse_event('error', {'type': 'error', 'message': str(exc)})
        yield _format_sse_event('done', {'type': 'done'})

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive'},
    )


@app.post('/api/v1/portfolio-feedback', response_class=PlainTextResponse)
def create_portfolio_feedback(payload: PortfolioFeedbackRequest) -> PlainTextResponse:
    try:
        lessons_payload = load_all_lessons_json_from_local_data()
        if not lessons_payload:
            raise HTTPException(status_code=400, detail='Khong tim thay du lieu lesson trong /data')
        feedback = generate_portfolio_feedback(lessons_payload, payload.portfolio_label)
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
        try:
            for event in stream_portfolio_feedback(lessons_payload, payload.portfolio_label):
                event_type = str(event.get('type', 'status'))
                yield _format_sse_event(event_type, event)
        except Exception as exc:
            yield _format_sse_event('error', {'type': 'error', 'message': str(exc)})
        yield _format_sse_event('done', {'type': 'done'})

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
