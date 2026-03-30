import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.llm import summarize_report
from app.schemas import SummaryRequest, SummaryResponse

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


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.post('/api/v1/summaries', response_model=SummaryResponse)
def create_summary(payload: SummaryRequest) -> SummaryResponse:
    try:
        summary = generate_summary(payload.report_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f'Invalid LLM response: {exc}') from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail='Unexpected summarization error') from exc

    return SummaryResponse(**summary)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'app.main:app',
        host='0.0.0.0',
        port=int(os.getenv('BACKEND_PORT', '8000')),
        reload=True,
    )
