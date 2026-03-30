import re

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
