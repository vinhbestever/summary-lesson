import hashlib
import json
import os
import re
from pathlib import Path


_SAFE_KEY_PATTERN = re.compile(r'[^a-zA-Z0-9._-]+')
LESSON_FEEDBACK_CACHE_VERSION = 'v5'


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _cache_dir() -> Path:
    raw_dir = os.getenv('FEEDBACK_CACHE_DIR', '').strip()
    if raw_dir:
        return Path(raw_dir)
    return _repo_root() / 'data' / 'feedback_cache'


def _sanitize_key(raw: str) -> str:
    sanitized = _SAFE_KEY_PATTERN.sub('_', raw.strip())
    return sanitized.strip('._') or 'default'


def _hash_payload(payload: dict[str, str]) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:16]


def lesson_feedback_cache_key(
    lesson_id: str | None,
    report_text: str | None,
    report_url: str | None,
    lesson_label: str | None,
) -> str:
    if lesson_id and lesson_id.strip():
        return f'lesson_{LESSON_FEEDBACK_CACHE_VERSION}_{_sanitize_key(lesson_id)}'
    payload_hash = _hash_payload(
        {
            'report_text': (report_text or '').strip(),
            'report_url': (report_url or '').strip(),
            'lesson_label': (lesson_label or '').strip(),
            'cache_version': LESSON_FEEDBACK_CACHE_VERSION,
        }
    )
    return f'lesson_input_{LESSON_FEEDBACK_CACHE_VERSION}_{payload_hash}'


def portfolio_feedback_cache_key() -> str:
    return 'portfolio_all_lessons'


def read_feedback_cache(cache_key: str) -> str | None:
    path = _cache_dir() / f'{_sanitize_key(cache_key)}.md'
    try:
        if not path.exists():
            return None
        content = path.read_text(encoding='utf-8').strip()
        return content or None
    except OSError:
        return None


def write_feedback_cache(cache_key: str, markdown: str) -> None:
    content = (markdown or '').strip()
    if not content:
        return

    cache_dir = _cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    target_path = cache_dir / f'{_sanitize_key(cache_key)}.md'
    temp_path = target_path.with_suffix('.md.tmp')
    temp_path.write_text(content, encoding='utf-8')
    os.replace(temp_path, target_path)
