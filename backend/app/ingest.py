import re
from pathlib import Path

import httpx


RINOEDU_REPORT_URL = 'https://rinoedu.ai/bao-cao-sau-buoi-hoc?erp_lesson_id={lesson_id}'


def _strip_html(html: str) -> str:
    text = re.sub(r'<script[\\s\\S]*?</script>', ' ', html, flags=re.IGNORECASE)
    text = re.sub(r'<style[\\s\\S]*?</style>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\\s+', ' ', text)
    return text.strip()


def fetch_report_text_from_url(report_url: str) -> str:
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        response = client.get(report_url)
        response.raise_for_status()

    extracted = _strip_html(response.text)
    if not extracted:
        raise ValueError('Could not extract text content from report_url')
    return extracted


def build_report_url_from_lesson_id(lesson_id: str) -> str:
    return RINOEDU_REPORT_URL.format(lesson_id=lesson_id)


def load_lesson_json_from_local_data(lesson_id: str) -> str | None:
    repo_root = Path(__file__).resolve().parents[2]
    data_path = repo_root / 'data' / f'lesson_{lesson_id}.json'
    if not data_path.exists():
        return None
    return data_path.read_text(encoding='utf-8').strip()


def load_all_lessons_json_from_local_data() -> list[dict[str, str]]:
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / 'data'
    if not data_dir.exists():
        return []

    items: list[dict[str, str]] = []
    for data_path in sorted(data_dir.glob('lesson_*.json')):
        raw_json_text = data_path.read_text(encoding='utf-8').strip()
        if not raw_json_text:
            continue
        lesson_id = data_path.stem.replace('lesson_', '', 1)
        items.append(
            {
                'lesson_id': lesson_id,
                'source_file': data_path.name,
                'raw_json_text': raw_json_text,
            }
        )
    return items
