import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.ingest import build_report_url_from_lesson_id, fetch_report_text_from_url
from app.llm import generate_lesson_feedback as generate_lesson_feedback_from_llm
from app.llm import summarize_report
from app.schemas import (
    LessonFeedbackRequest,
    LessonFeedbackResponse,
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


def resolve_report_text(payload: ReportInputRequest) -> str:
    if payload.report_text:
        return payload.report_text

    if payload.report_url:
        return fetch_report_text_from_url(payload.report_url)

    if payload.lesson_id:
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


@app.post('/api/v1/lesson-feedback', response_model=LessonFeedbackResponse)
def create_lesson_feedback(payload: LessonFeedbackRequest) -> LessonFeedbackResponse:
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

    return LessonFeedbackResponse(**feedback)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=int(os.getenv('BACKEND_PORT', '8000')),
        reload=True,
    )
